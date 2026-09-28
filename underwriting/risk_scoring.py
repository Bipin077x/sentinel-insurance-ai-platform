from typing import Tuple, Dict, Any
from core.models import Application

def evaluate_risk(app: Application) -> Tuple[str, float, str]:
    """
    Evaluates risk using an actuarial formula and generates a narrative.
    Returns (risk_tier, suggested_premium, narrative)
    """
    # 1. Base Premium (5% of trip cost)
    base_premium = app.trip_cost * 0.05
    multiplier = 1.0
    
    # 2. Risk Multipliers
    if app.age > 65:
        multiplier += 0.5
    elif app.age > 50:
        multiplier += 0.2
        
    if app.pre_existing_conditions:
        multiplier += 0.75
        
    if "skiing" in app.planned_activities or "scuba diving" in app.planned_activities:
        multiplier += 0.3
        
    suggested_premium = base_premium * multiplier
    
    # 3. Determine Tier
    if multiplier <= 1.2:
        risk_tier = "Low"
    elif multiplier <= 1.8:
        risk_tier = "Medium"
    else:
        risk_tier = "High"
        
    # 4. Narrative (Mock LLM)
    narrative = f"Applicant is {app.age} years old traveling to {app.destination} for {app.trip_duration_days} days. "
    if app.pre_existing_conditions:
        narrative += "Pre-existing conditions noted, significantly increasing risk. "
    
    if multiplier > 1.0:
        narrative += f"Overall risk is elevated (multiplier {multiplier:.2f})."
    else:
        narrative += "Standard risk profile."
        
    return risk_tier, suggested_premium, narrative
