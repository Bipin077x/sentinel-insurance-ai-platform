from typing import Dict, Any, Optional

def should_auto_decide(
    confidence: float, 
    stakes_value: Optional[float], 
    function_type: str, 
    escalation_policy: Dict[str, Any],
    override_score: float = 0.0,
    override_type: str = "fraud",
    hard_ceiling: Optional[float] = None
) -> tuple[bool, str]:
    """
    Determines if a decision should be automated or routed to a human review queue.

    hard_ceiling: if provided and stakes_value exceeds it, the decision is immediately
    escalated as 'amount_ceiling' before any confidence or override checks are performed.
    This is a gate-layer hard stop — distinct from the extraction-layer sanity checks
    in validators.py.
    
    escalation_policy format example:
    {
        "underwriting": {
            "default_confidence_threshold": 0.9,
            "stakes_thresholds": [
                {"max_stakes": 5000, "confidence_threshold": 0.8},
                {"max_stakes": 50000, "confidence_threshold": 0.9},
                {"max_stakes": None, "confidence_threshold": 0.95}
            ]
        }
    }
    """
    policy = escalation_policy.get(function_type)
    if not policy:
        # If no policy is defined for the function, default to human review (safe fallback)
        return False, f"no_policy_defined_for_{function_type}"

    # 0. Hard amount ceiling (gate-layer) — fires before any other check.
    # Distinct from extraction-layer sanity ceilings in validators.py.
    if hard_ceiling is not None and stakes_value is not None and stakes_value > hard_ceiling:
        return False, f"amount_ceiling (amount {stakes_value:.2f} > hard ceiling {hard_ceiling:.2f})"
        
    # 1. Deterministic Overrides
    # High override score completely bypasses calibration confidence and forces human review
    override_threshold = policy.get("override_threshold", 1.0)
    if override_score >= override_threshold:
        return False, f"{override_type}_override ({override_type}_score {override_score} >= {override_threshold})"
        
    thresholds = policy.get("stakes_thresholds", [])
    
    # If stakes_value is provided, find the applicable threshold tier
    if stakes_value is not None:
        # Sort thresholds by max_stakes to evaluate in ascending order
        # Treat None as infinity
        sorted_thresholds = sorted(
            thresholds, 
            key=lambda t: t.get("max_stakes") if t.get("max_stakes") is not None else float('inf')
        )
        
        for tier in sorted_thresholds:
            max_stakes = tier.get("max_stakes")
            if max_stakes is None or stakes_value <= max_stakes:
                required_confidence = tier.get("confidence_threshold", 1.0)
                if confidence >= required_confidence:
                    return True, "auto_decided"
                else:
                    return False, f"low_calibration_confidence (confidence {confidence} < threshold {required_confidence} for stakes {stakes_value})"
                
    # Fallback to default if no stakes matched or stakes_value is None
    default_threshold = policy.get("default_confidence_threshold", 1.0)
    if confidence >= default_threshold:
        return True, "auto_decided"
    return False, f"low_calibration_confidence (confidence {confidence} < default_threshold {default_threshold})"
