import pytest
from core.faithfulness import verify_faithfulness

def test_verify_faithfulness_valid():
    cited_rules = ["Age Limit Rule", "Pre-existing Condition Rule"]
    cited_fields = ["age", "trip_cost"]
    
    actual_rules = ["Age Limit Rule", "Destination Risk Rule", "Pre-existing Condition Rule"]
    extracted_keys = ["id", "age", "destination", "trip_cost", "pre_existing_conditions"]
    
    errors = verify_faithfulness(cited_rules, cited_fields, actual_rules, extracted_keys)
    assert len(errors) == 0

def test_verify_faithfulness_fabrication():
    cited_rules = ["Alien Invasion Coverage", "Age Limit Rule"]
    cited_fields = ["blood_type", "age"]
    
    actual_rules = ["Age Limit Rule", "Destination Risk Rule"]
    extracted_keys = ["id", "age", "destination"]
    
    errors = verify_faithfulness(cited_rules, cited_fields, actual_rules, extracted_keys)
    
    assert len(errors) == 2
    assert any("Alien Invasion Coverage" in err for err in errors)
    assert any("blood_type" in err for err in errors)
