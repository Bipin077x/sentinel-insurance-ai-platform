import pytest
from core.redaction import redact_text, redact_data

def test_redact_text():
    text = "My SSN is 123-45-6789 and I have diabetes and CANCER. Call me at 555-123-4567 or email at john.doe@example.com. Born on Jan 15, 1980."
    redacted = redact_text(text)
    
    assert "123-45-6789" not in redacted
    assert "[REDACTED_SSN]" in redacted
    
    assert "diabetes" not in redacted.lower()
    assert "[REDACTED_PHI]" in redacted
    
    assert "CANCER" not in redacted
    assert "[REDACTED_PHI]" in redacted
    
    assert "555-123-4567" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    
    assert "john.doe@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    
    assert "Jan 15, 1980" not in redacted
    assert "[REDACTED_DOB]" in redacted

def test_redact_data():
    snapshot = {
        "raw_text": "Patient has HIV.",
        "nested": {
            "ssn": "987-65-4321",
            "age": 45,
            "conditions": ["asthma", "healthy"]
        }
    }
    
    redacted = redact_data(snapshot)
    
    # Original should be untouched (if deepcopied before calling or just structurally)
    # redact_data creates new dicts for branches
    assert redacted["raw_text"] == "Patient has [REDACTED_PHI]."
    assert redacted["nested"]["ssn"] == "[REDACTED_SSN]"
    assert redacted["nested"]["age"] == 45
    assert redacted["nested"]["conditions"][0] == "[REDACTED_PHI]"
    assert redacted["nested"]["conditions"][1] == "healthy"
