import pytest
from core.database import init_db, SessionLocal
from underwriting.generate_apps import generate_synthetic_applications
from underwriting.run_underwriting import run_pipeline
from eval.fairness_eval import run_fairness_eval

def test_fairness_eval_detects_proxy_bias():
    # 1. Setup DB
    init_db()
    db = SessionLocal()
    
    # 2. Generate apps with injected proxy bias
    generate_synthetic_applications()
    
    # 3. Run the underwriting pipeline to populate decisions
    run_pipeline()
    
    # 4. Run the fairness evaluation
    report = run_fairness_eval(db, "synthetic_applications.json")
    
    # Asserts
    # Group B was predominantly assigned to Scenarios 2 (North Korea/Decline) and 3 (Switzerland/Loading).
    # Group A was predominantly Scenarios 0 (France/Accept) and 1 (Italy/Decline).
    
    assert "Group A" in report["groups"]
    assert "Group B" in report["groups"]
    
    # Group B should likely have a lower approval rate due to the proxy bias
    # Or at least, we should detect a proxy correlation flag for North Korea or Switzerland
    assert len(report["proxy_correlation_flags"]) > 0, "Failed to detect the injected proxy correlation!"
    
    proxy_flags_text = " ".join(report["proxy_correlation_flags"])
    assert "North Korea" in proxy_flags_text or "Switzerland" in proxy_flags_text or "France" in proxy_flags_text, \
        f"Did not flag the correct proxy destinations. Flags: {proxy_flags_text}"
