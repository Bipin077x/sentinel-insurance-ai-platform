"""
ingestion/quality_gate.py — Quality gating for OCR documents (Phase 9)
"""

from typing import Tuple
from ingestion.document_parser import ParsedDocument

def gate_document_quality(parsed: ParsedDocument) -> Tuple[bool, str]:
    """
    Returns (True, "") if confidence >= 0.70.
    Returns (False, reason) if confidence < 0.70.
    """
    if parsed.confidence >= 0.70:
        return True, ""
    else:
        return False, f"Document confidence score {parsed.confidence:.2f} is below the 0.70 threshold. Manual review required."
