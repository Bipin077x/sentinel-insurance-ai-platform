from typing import Dict, Any

# Global state to hold the validated ruleset and its hash
_ACTIVE_RULESET = None
_ACTIVE_RULESET_HASH = None

def init_compliance():
    """Initializes and validates compliance settings on startup."""
    global _ACTIVE_RULESET, _ACTIVE_RULESET_HASH
    if _ACTIVE_RULESET is None:
        from core.compliance_loader import load_and_validate_compliance
        _ACTIVE_RULESET, _ACTIVE_RULESET_HASH = load_and_validate_compliance()

def get_active_compliance_ruleset_hash() -> str:
    """Returns the cryptographic hash of the active compliance ruleset."""
    if _ACTIVE_RULESET_HASH is None:
        init_compliance()
    return _ACTIVE_RULESET_HASH

def check_compliance_rule(rule_name: str) -> Any:
    """Returns the value of a specific compliance rule."""
    if _ACTIVE_RULESET is None:
        init_compliance()
    rules = _ACTIVE_RULESET.get("rules", {})
    return rules.get(rule_name)
