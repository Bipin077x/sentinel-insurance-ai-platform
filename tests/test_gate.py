from core.gate import should_auto_decide

def test_should_auto_decide_no_policy():
    # If no policy exists for function, should return False
    assert should_auto_decide(0.99, 100, "unknown_function", {}) == False

def test_should_auto_decide_default_threshold():
    policy = {
        "brokerage": {
            "default_confidence_threshold": 0.8
        }
    }
    # No stakes provided, uses default
    assert should_auto_decide(0.85, None, "brokerage", policy) == True
    assert should_auto_decide(0.75, None, "brokerage", policy) == False

def test_should_auto_decide_stakes_thresholds():
    policy = {
        "underwriting": {
            "default_confidence_threshold": 0.95,
            "stakes_thresholds": [
                {"max_stakes": 1000, "confidence_threshold": 0.7},
                {"max_stakes": 10000, "confidence_threshold": 0.85},
                {"max_stakes": None, "confidence_threshold": 0.95}
            ]
        }
    }
    
    # Stakes = 500, matches first tier (max_stakes=1000, conf=0.7)
    assert should_auto_decide(0.75, 500, "underwriting", policy) == True
    assert should_auto_decide(0.65, 500, "underwriting", policy) == False
    
    # Stakes = 5000, matches second tier (max_stakes=10000, conf=0.85)
    assert should_auto_decide(0.86, 5000, "underwriting", policy) == True
    assert should_auto_decide(0.84, 5000, "underwriting", policy) == False
    
    # Stakes = 50000, matches third tier (max_stakes=None, conf=0.95)
    assert should_auto_decide(0.96, 50000, "underwriting", policy) == True
    assert should_auto_decide(0.94, 50000, "underwriting", policy) == False
