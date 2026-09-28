import re
from typing import Any, Dict, List, Union
import copy

# Hardcode config flag - Cannot be bypassed without explicit override logic
REDACTION_REQUIRED = True

# POC-level RegEx Patterns
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
DOB_PATTERN = re.compile(r'\b(?:born\s+on\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b', re.IGNORECASE)
DOB_PATTERN_NUM = re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b')

# POC-level PHI keywords
PHI_KEYWORDS = [
    "cancer", "diabetes", "heart disease", "hypertension", "stroke", 
    "asthma", "hiv", "aids", "tumor", "chemotherapy", "dialysis"
]

def redact_text(text: str) -> str:
    """
    Applies pattern-based redaction to string content.
    WARNING: This is a POC and NOT sufficient for production HIPAA/GDPR compliance.
    """
    if not isinstance(text, str):
        return text
        
    redacted = text
    
    # 1. Regex Replacements
    redacted = SSN_PATTERN.sub("[REDACTED_SSN]", redacted)
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", redacted)
    redacted = DOB_PATTERN.sub("[REDACTED_DOB]", redacted)
    redacted = DOB_PATTERN_NUM.sub("[REDACTED_DOB]", redacted)
    
    # 2. Keyword Replacements
    for keyword in PHI_KEYWORDS:
        # Simple case-insensitive replacement (naive)
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        redacted = pattern.sub("[REDACTED_PHI]", redacted)
        
    return redacted

def redact_data(data: Union[Dict, List, Any]) -> Union[Dict, List, Any]:
    """
    Recursively traverses dictionaries/lists and applies redact_text to all string values.
    """
    if not REDACTION_REQUIRED:
        # In a real system, disabling this would require extreme logging logic here
        return data
        
    if isinstance(data, dict):
        return {k: redact_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [redact_data(v) for v in data]
    elif isinstance(data, str):
        return redact_text(data)
    else:
        return data

def redact_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to cleanly redact an inputs_snapshot without mutating the original.
    """
    # Create a deepcopy so we don't accidentally mutate in-memory objects shared elsewhere
    safe_copy = copy.deepcopy(snapshot)
    return redact_data(safe_copy)
