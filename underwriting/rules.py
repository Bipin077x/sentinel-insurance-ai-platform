from typing import List
from core.models import Application, RuleResult

EXCLUDED_DESTINATIONS = ["North Korea", "Syria", "Mars"]
EXCLUDED_ACTIVITIES = ["base jumping", "free solo climbing", "wingsuit flying"]
MAX_AGE = 85

def check_rules(app: Application) -> List[RuleResult]:
    """
    Runs deterministic checks for underwriting eligibility.
    """
    results = []
    
    # 1. Age Limit
    within_age = app.age <= MAX_AGE
    results.append(RuleResult(
        rule_name="age_limit",
        passed=within_age,
        detail=f"Age {app.age} exceeds maximum limit of {MAX_AGE}" if not within_age else "Within age limits"
    ))
    
    # 2. Excluded Destination
    dest_allowed = app.destination not in EXCLUDED_DESTINATIONS
    results.append(RuleResult(
        rule_name="excluded_destination",
        passed=dest_allowed,
        detail=f"Destination {app.destination} is excluded" if not dest_allowed else "Destination permitted"
    ))
    
    # 3. Excluded Activities
    found_excluded_acts = [act for act in app.planned_activities if act.lower() in EXCLUDED_ACTIVITIES]
    acts_allowed = len(found_excluded_acts) == 0
    results.append(RuleResult(
        rule_name="excluded_activities",
        passed=acts_allowed,
        detail=f"Activities excluded: {', '.join(found_excluded_acts)}" if not acts_allowed else "Activities permitted"
    ))
    
    return results
