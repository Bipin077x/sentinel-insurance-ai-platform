from typing import Tuple, List
from core.models import Application

def evaluate_referral_score(app: Application) -> Tuple[float, List[str]]:
    """
    Computes a deterministic referral_score based on risk concentration and treaty limits.
    Returns (score, list of flags).
    """
    score = 0.0
    flags = []
    
    # 1. High Exposure (Treaty Limit)
    if app.trip_cost >= 5000:
        score += 1.0
        flags.append("treaty_limit_exposure")
        
    # 2. Factor Stacking
    factor_score = 0.0
    
    # Age factor
    if app.age >= 70:
        factor_score += 0.4
        flags.append("age_factor")
        
    # Destination factor
    high_risk_destinations = ["USA", "Switzerland", "Canada"]
    if app.destination in high_risk_destinations:
        factor_score += 0.4
        flags.append("destination_factor")
        
    # Pre-existing condition factor
    if app.pre_existing_conditions:
        factor_score += 0.4
        flags.append("pre_existing_factor")
        
    # Watchlist Flags
    if "bad guy" in app.id.lower(): # Just a mock watchlist check
        score += 1.0
        flags.append("watchlist_match")
        
    # Sum factor stacking and add to total score
    score += factor_score
    
    # Cap at 1.0
    final_score = min(score, 1.0)
    
    return final_score, flags
