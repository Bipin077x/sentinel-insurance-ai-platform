from typing import Dict, Any
from core.models import Document
from core.redaction import redact_text

def process_intake(raw_claim_data: Dict[str, Any]) -> Document:
    """
    Normalizes a raw claim submission into a standard Document format
    before sending it to extraction.
    """
    doc_id = f"doc_{raw_claim_data['claim_id']}"
    
    # In a real system, this would handle OCR, format normalization, etc.
    # For now, we just wrap the raw text.
    redacted_text = redact_text(raw_claim_data["raw_text"])
    
    return Document(
        id=doc_id,
        doc_type="claim_submission",
        raw_text=redacted_text,
        source_metadata={
            "claim_id": raw_claim_data["claim_id"],
            "policy_id": raw_claim_data["policy_id"],
            "date_filed": raw_claim_data["date_filed"]
        }
    )
