import pytest
from core.models import Claim, Application, ClientNeeds
from core.validators import validate_claim, validate_application, validate_client_needs
from datetime import datetime, timezone, timedelta

def test_validate_claim_bounds():
    now = datetime.now(timezone.utc)
    
    # Valid claim
    valid = Claim(
        id="CLM-1", policy_id="POL-1", date_filed=now - timedelta(days=1),
        claim_type="Medical", amount=500.0, cause="Sick", evidence_list=[]
    )
    assert not validate_claim(valid)
    
    # Negative amount
    invalid_amount = valid.model_copy(update={"amount": -100.0})
    errs = validate_claim(invalid_amount)
    assert len(errs) == 1
    assert "greater than 0" in errs[0]
    
    # Future date
    invalid_date = valid.model_copy(update={"date_filed": now + timedelta(days=1)})
    errs = validate_claim(invalid_date)
    assert len(errs) == 1
    assert "future" in errs[0]

def test_validate_application_bounds():
    # Valid app
    valid = Application(
        id="APP-1", age=30, destination="France", trip_cost=1000.0,
        pre_existing_conditions=False, trip_duration_days=10, planned_activities=[]
    )
    assert not validate_application(valid)
    
    # Impossible age
    invalid_age = valid.model_copy(update={"age": 400})
    errs = validate_application(invalid_age)
    assert len(errs) == 1
    assert "bounds" in errs[0]
    
    # Negative cost
    invalid_cost = valid.model_copy(update={"trip_cost": -50.0})
    errs = validate_application(invalid_cost)
    assert len(errs) == 1
    assert "negative" in errs[0]

def test_validate_client_needs_bounds():
    # Valid needs
    valid = ClientNeeds(
        client_id="CLI-1", destination="Global", duration_days=10,
        coverage_priorities=["medical"], budget_signal="standard"
    )
    assert not validate_client_needs(valid)
    
    # Negative duration
    invalid_dur = valid.model_copy(update={"duration_days": -5})
    errs = validate_client_needs(invalid_dur)
    assert len(errs) == 1
    assert "greater than 0" in errs[0]
