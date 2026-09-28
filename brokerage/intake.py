from typing import Dict, Any
from core.models import Document

def process_intake(raw_client_data: Dict[str, Any]) -> Document:
    doc_id = f"doc_{raw_client_data['client_id']}"
    
    from core.redaction import redact_text
    redacted_text = redact_text(raw_client_data["raw_text"])
    return Document(
        id=doc_id,
        doc_type="client_needs",
        raw_text=redacted_text,
        source_metadata={
            "client_id": raw_client_data["client_id"]
        }
    )
