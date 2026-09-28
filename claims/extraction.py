import json
import re
from datetime import datetime
from core.models import Document, Claim
from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt

from core.validators import validate_claim

class ExtractionValidationError(Exception):
    def __init__(self, errors: list[str], prompt_hash: str):
        self.errors = errors
        self.prompt_hash = prompt_hash
        super().__init__("Extraction validation failed")

def extract_claim_info(document: Document) -> tuple[Claim, str]:
    """
    Extracts structured claim data from the raw document text via LLM.
    Runs validators immediately; fails closed by raising an exception.
    """
    template, prompt_hash = load_prompt("claims_extraction", "v1")
    prompt = template.replace("{{document_text}}", document.raw_text) \
                     .replace("{{claim_id}}", document.source_metadata.get("claim_id", "")) \
                     .replace("{{policy_id}}", document.source_metadata.get("policy_id", "")) \
                     .replace("{{date_filed}}", document.source_metadata.get("date_filed", ""))
    
    # We invoke the mock wrapper that pretends to be an LLM
    def mock_llm_extraction(p, schema):
        text = document.raw_text.lower()
        
        amount = 0.0
        amount_match = re.search(r'\$(-?\d+(?:\.\d{2})?)', text)
        if amount_match:
            amount = float(amount_match.group(1))
            
        cause = "unknown"
        if "weather" in text:
            cause = "bad weather"
        elif "bankrupt" in text:
            cause = "airline bankruptcy"
        elif "skydiving" in text:
            cause = "extreme sports injury"
        elif "illness" in text:
            cause = "illness"
        elif "fell down" in text:
            cause = "medical emergency"
        elif "missed flight" in text:
            cause = "missed flight"
        elif "personal reasons" in text:
            cause = "personal reasons"
            
        return json.dumps({
            "id": document.source_metadata.get("claim_id", ""),
            "policy_id": document.source_metadata.get("policy_id", ""),
            "date_filed": document.source_metadata.get("date_filed", ""),
            "incident_date": document.source_metadata.get("incident_date", document.source_metadata.get("date_filed", "")),
            "claim_type": "trip_cancellation",
            "amount": amount,
            "cause": cause,
            "evidence_list": []
        })

    claim = call_llm_with_schema(prompt, Claim, mock_llm_extraction)
    
    # Phase 2 constraint: validate immediately
    validation_errors = validate_claim(claim)
    if validation_errors:
        raise ExtractionValidationError(validation_errors, prompt_hash)
        
    return claim, prompt_hash
