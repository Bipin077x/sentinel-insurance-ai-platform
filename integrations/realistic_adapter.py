import requests
import xml.etree.ElementTree as ET
import uuid
import time
import hashlib
from typing import Optional, Tuple
from core.models import Decision, FunctionType, DecisionStatus
from datetime import datetime, timezone

class IntegrationError(Exception):
    pass

class IntegrationPartialFailure(Exception):
    def __init__(self, message: str, details: dict):
        self.details = details
        super().__init__(message)
        
class IntegrationTimeout(Exception):
    pass

class LegacyPolicyAdminAdapter:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    def _generate_correlation_id(self, decision_id: str) -> str:
        # Traceable correlation ID derived from decision_id but distinct for the external call
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{decision_id}-corr"))
        
    def _generate_idempotency_key(self, decision_id: str, payload_hash: str) -> str:
        # Deterministic idempotency key based on decision + payload content
        raw = f"{decision_id}-{payload_hash}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()
        
    def _serialize_decision_to_xml(self, decision: Decision) -> str:
        root = ET.Element("PolicyUpdate")
        
        app_el = ET.SubElement(root, "ApplicationId")
        app_el.text = decision.subject_id
        
        decision_el = ET.SubElement(root, "Decision")
        decision_el.text = decision.outcome
        
        conf_el = ET.SubElement(root, "ConfidenceScore")
        conf_el.text = str(decision.confidence_score)
        
        reasoning_el = ET.SubElement(root, "ReasoningText")
        reasoning_el.text = decision.reasoning_text
        
        status_el = ET.SubElement(root, "Status")
        status_el.text = decision.status.value
        
        return ET.tostring(root, encoding="unicode")
        
    def _parse_xml_to_decision(self, xml_str: str) -> Decision:
        root = ET.fromstring(xml_str)
        
        subject_id = root.find("ApplicationId").text
        outcome = root.find("Decision").text
        confidence_score = float(root.find("ConfidenceScore").text)
        reasoning_text = root.find("ReasoningText").text
        status_val = root.find("Status").text
        
        # We reconstruct a partial Decision to prove parsing works.
        # (Missing fields that aren't serialized to the legacy system will be ignored/defaulted)
        return Decision(
            id="parsed_id", # Not serialized
            function_type=FunctionType.UNDERWRITING,
            subject_id=subject_id,
            outcome=outcome,
            confidence_score=confidence_score,
            confidence_source="parsed",
            rules_fired=[],
            reasoning_text=reasoning_text,
            model_version="parsed-1",
            timestamp=datetime.now(timezone.utc),
            status=DecisionStatus(status_val),
            compliance_ruleset_hash="",
            prompt_hash=""
        )

    def _parse_xml_response(self, xml_str: str) -> Tuple[Optional[str], ET.Element]:
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            raise IntegrationError("Failed to parse response XML")
            
        header = root.find("Header")
        body = root.find("Body")
        
        correlation_id = header.find("CorrelationId").text if header is not None and header.find("CorrelationId") is not None else None
        
        return correlation_id, body
        
    def push_decision(self, decision: Decision, timeout_seconds: int = 5) -> Tuple[bool, int]:
        correlation_id = self._generate_correlation_id(decision.id)
        
        body_xml = self._serialize_decision_to_xml(decision)
        payload_hash = hashlib.md5(body_xml.encode('utf-8')).hexdigest()
        idempotency_key = self._generate_idempotency_key(decision.id, payload_hash)
        
        headers = {
            "CorrelationId": correlation_id,
            "IdempotencyKey": idempotency_key,
            "Content-Type": "application/xml"
        }
        
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<Envelope>
    <Header>
        <CorrelationId>{correlation_id}</CorrelationId>
    </Header>
    <Body>{body_xml}</Body>
</Envelope>"""
        
        # 1. Initial POST with Network Retry loop
        max_network_retries = 3
        resp = None
        for attempt in range(max_network_retries):
            resp = requests.post(f"{self.base_url}/policy/update", data=envelope, headers=headers)
            if resp.status_code >= 500:
                # Network/Server error, retry using SAME idempotency key
                time.sleep(0.5)
                continue
            elif resp.status_code == 202:
                break
            else:
                raise IntegrationError(f"Unexpected status: {resp.status_code}")
                
        if resp is None or resp.status_code != 202:
            raise IntegrationError("Failed after network retries")
            
        _, body = self._parse_xml_response(resp.text)
        job_id = body.find("JobId").text
        apply_count_el = body.find("ApplyCount")
        initial_apply_count = int(apply_count_el.text) if apply_count_el is not None else 0
        
        # 2. Poll for async confirmation
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            poll_resp = requests.get(f"{self.base_url}/status/{job_id}", headers={"CorrelationId": correlation_id})
            if poll_resp.status_code == 200:
                _, poll_body = self._parse_xml_response(poll_resp.text)
                status = poll_body.find("Status").text
                
                if status == "CONFIRMED":
                    return True, initial_apply_count
                elif status == "PARTIAL_SUCCESS":
                    # Extract specifics
                    details = {}
                    for sys_el in poll_body.findall(".//System"):
                        details[sys_el.attrib.get("name", "Unknown")] = sys_el.text
                    raise IntegrationPartialFailure("Write succeeded partially", details)
                elif status == "FAILED":
                    raise IntegrationError("Async job failed")
                elif status == "PENDING" or status == "Retrieved":
                    time.sleep(0.5)
                    continue
            else:
                time.sleep(0.5)
                
        raise IntegrationTimeout(f"Timed out waiting for job {job_id} to confirm")
