import uvicorn
from multiprocessing import Process
import time
import requests
import xml.etree.ElementTree as ET
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from integrations.realistic_adapter import (
    LegacyPolicyAdminAdapter, 
    IntegrationError, 
    IntegrationPartialFailure, 
    IntegrationTimeout
)
from core.models import Decision, FunctionType, DecisionStatus
from datetime import datetime, timezone

def run_server():
    uvicorn.run("integrations.realistic_mock_server:app", host="127.0.0.1", port=8000, log_level="error")

def get_server_apply_count():
    resp = requests.get("http://127.0.0.1:8000/mock/state")
    return resp.json().get("backend_apply_count", 0)

def simulate_pipeline_runner(adapter: LegacyPolicyAdminAdapter, decision: Decision):
    """
    Simulates what the pipeline runner does when catching integration exceptions:
    It updates the decision state (e.g. to PENDING_REVIEW) and logs the failure, 
    ensuring it lands in the Phase 10 review queue instead of silently retrying.
    """
    try:
        success, apply_count = adapter.push_decision(decision)
        return success, apply_count, decision
    except IntegrationPartialFailure as e:
        decision.status = DecisionStatus.PENDING_REVIEW
        decision.reasoning_text += f"\nIntegration Partial Failure: {json.dumps(e.details)}"
        return False, None, decision
    except IntegrationTimeout as e:
        decision.status = DecisionStatus.PENDING_REVIEW
        decision.reasoning_text += f"\nIntegration Timeout: {str(e)}"
        return False, None, decision

def run_tests():
    adapter = LegacyPolicyAdminAdapter("http://127.0.0.1:8000")
    
    print("--- 1. Round-Trip XML Translation Test ---")
    decision = Decision(
        id="dec_roundtrip",
        function_type=FunctionType.UNDERWRITING,
        subject_id="APP-999",
        outcome="accept",
        confidence_score=0.95,
        confidence_source="mock",
        rules_fired=[],
        reasoning_text="Standard risk profile",
        model_version="test-1",
        timestamp=datetime.now(timezone.utc),
        status=DecisionStatus.AUTO_DECIDED,
        compliance_ruleset_hash="xyz",
        prompt_hash="abc"
    )
    xml_out = adapter._serialize_decision_to_xml(decision)
    print(f"Generated XML:\n{xml_out}")
    parsed_decision = adapter._parse_xml_to_decision(xml_out)
    
    print(f"Parsed Outcome: {parsed_decision.outcome} == {decision.outcome}")
    print(f"Parsed Subject: {parsed_decision.subject_id} == {decision.subject_id}")
    print(f"Parsed Confidence: {parsed_decision.confidence_score} == {decision.confidence_score}")
    print(f"Parsed Status: {parsed_decision.status} == {decision.status}")
    assert parsed_decision.outcome == decision.outcome
    assert parsed_decision.subject_id == decision.subject_id
    assert parsed_decision.confidence_score == decision.confidence_score
    assert parsed_decision.status == decision.status
    print("-> XML Round-trip passed exactly.\n")
    
    print("--- 2. Idempotency Test (Network Retry / Double-Apply Check) ---")
    requests.post("http://127.0.0.1:8000/mock/reset")
    decision.id = "dec_idempotency"
    decision.outcome = "force_503_once" # This triggers the mock server to return 503 on the first attempt
    
    # Send the decision. The adapter will internally catch the 503 and retry with the SAME idempotency key.
    # The server will accept the retry because the cache prevents the 503 logic from triggering again, 
    # BUT wait... if it returns 503, it shouldn't have cached it?
    # Our mock server hack: it caches the job_id, but returns 503. The NEXT try with the same key 
    # will hit the `if idempotency_key in idempotency_cache:` block and return `202 Accepted (Retrieved)`!
    # Because it returns Retrieved, `backend_apply_count` is NOT incremented the second time.
    start_count = get_server_apply_count()
    success, return_count = adapter.push_decision(decision)
    end_count = get_server_apply_count()
    
    print(f"Backend Apply Count before adapter call: {start_count}")
    print(f"Backend Apply Count after adapter internally retried 503: {end_count}")
    print(f"Change in Apply Count: {end_count - start_count} (should be exactly 1 despite retry)")
    assert end_count - start_count == 1
    print("-> Idempotency logic correctly prevented double-application during network retries.\n")
    
    print("--- 3. Partial Failure Test & Review Queue Routing ---")
    requests.post("http://127.0.0.1:8000/mock/reset")
    decision.id = "dec_partial"
    decision.outcome = "partial_fail_sim"
    decision.status = DecisionStatus.AUTO_DECIDED
    
    start_count = get_server_apply_count()
    success, _, updated_decision = simulate_pipeline_runner(adapter, decision)
    end_count = get_server_apply_count()
    
    print(f"Success returned: {success}")
    print(f"New Decision Status: {updated_decision.status}")
    print(f"New Reasoning Text: {updated_decision.reasoning_text}")
    print(f"Backend hit count for this operation: {end_count - start_count}")
    
    assert not success
    assert updated_decision.status == DecisionStatus.PENDING_REVIEW
    assert "PolicyAdmin" in updated_decision.reasoning_text
    print("-> Partial failure cleanly caught, explicitly logged to review queue, and NOT blindly retried.\n")
    
    print("--- 4. Timeout Test & Review Queue Routing ---")
    requests.post("http://127.0.0.1:8000/mock/reset")
    decision.id = "dec_timeout"
    decision.outcome = "timeout_sim"
    decision.status = DecisionStatus.AUTO_DECIDED
    decision.reasoning_text = "Standard risk profile"
    
    start_count = get_server_apply_count()
    success, _, updated_decision = simulate_pipeline_runner(adapter, decision)
    end_count = get_server_apply_count()
    
    print(f"New Decision Status: {updated_decision.status}")
    print(f"New Reasoning Text: {updated_decision.reasoning_text}")
    print(f"Backend hit count for this operation: {end_count - start_count}")
    assert updated_decision.status == DecisionStatus.PENDING_REVIEW
    assert "Integration Timeout" in updated_decision.reasoning_text
    print("-> Timeout case correctly pushed decision into unconfirmed/review state.\n")

if __name__ == "__main__":
    server_process = Process(target=run_server)
    server_process.start()
    try:
        time.sleep(2) # wait for server to start
        run_tests()
    finally:
        server_process.terminate()
        server_process.join()
