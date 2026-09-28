from datetime import datetime, timezone
from typing import List
from core.models import Claim, Application, ClientNeeds

def validate_claim(claim: Claim) -> List[str]:
    """Validates extracted Claim data against deterministic sanity bounds."""
    errors = []
    
    if claim.amount <= 0:
        errors.append(f"amount ({claim.amount}) must be greater than 0")
    if claim.amount >= 2_000_000:
        errors.append(f"amount ({claim.amount}) exceeds absolute sanity ceiling of 2,000,000")
        
    now = datetime.now(timezone.utc)
    if claim.date_filed > now:
        errors.append(f"date_filed ({claim.date_filed}) cannot be in the future")
        
    if not claim.policy_id:
        errors.append("policy_id is missing")
    if not claim.claim_type:
        errors.append("claim_type is missing")
        
    return errors

def validate_application(app: Application) -> List[str]:
    """Validates extracted Application data against deterministic sanity bounds."""
    errors = []
    
    if app.age < 0 or app.age > 120:
        errors.append(f"age ({app.age}) is out of logical bounds (0-120)")
        
    if app.trip_cost < 0:
        errors.append(f"trip_cost ({app.trip_cost}) cannot be negative")
    if app.trip_cost >= 500_000:
        errors.append(f"trip_cost ({app.trip_cost}) exceeds absolute sanity ceiling of 500,000")
        
    if app.trip_duration_days <= 0:
        errors.append(f"trip_duration_days ({app.trip_duration_days}) must be greater than 0")
        
    if not app.destination:
        errors.append("destination is missing")
        
    return errors

def validate_client_needs(needs: ClientNeeds) -> List[str]:
    """Validates extracted ClientNeeds data against deterministic sanity bounds."""
    errors = []
    
    if needs.duration_days <= 0:
        errors.append(f"duration_days ({needs.duration_days}) must be greater than 0")
        
    if not needs.destination:
        errors.append("destination is missing")
        
    return errors
