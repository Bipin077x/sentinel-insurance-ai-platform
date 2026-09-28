from typing import Dict, Any
from core.models import Document
from core.redaction import redact_text

def process_intake(raw_app_data: Dict[str, Any]) -> Document:
    """
    Normalizes a raw application submission into a standard Document format.
    Redacts raw text immediately.
    """
    doc_id = f"doc_{raw_app_data['app_id']}"
    
    redacted_text = redact_text(raw_app_data["raw_text"])
    
    return Document(
        id=doc_id,
        doc_type="insurance_application",
        raw_text=redacted_text,
        source_metadata={
            "app_id": raw_app_data["app_id"],
            "submission_date": raw_app_data["metadata"]["submission_date"]
        }
    )
