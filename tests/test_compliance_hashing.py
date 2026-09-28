import os
import pytest
import json
import yaml
import shutil
from pathlib import Path
from core.database import SessionLocal, init_db, ComplianceHistoryRecord, engine, Base
from core.compliance_loader import load_and_validate_compliance

COMPLIANCE_DIR = Path("compliance")
COMPLIANCE_YAML = COMPLIANCE_DIR / "compliance_rules.yaml"
MANIFEST_JSON = COMPLIANCE_DIR / "manifest.json"

@pytest.fixture(autouse=True)
def setup_test_env():
    # Setup test DB
    Base.metadata.drop_all(bind=engine)
    init_db()
    
    # Backup files
    if COMPLIANCE_YAML.exists():
        shutil.copy(COMPLIANCE_YAML, COMPLIANCE_YAML.with_suffix(".bak"))
    if MANIFEST_JSON.exists():
        shutil.copy(MANIFEST_JSON, MANIFEST_JSON.with_suffix(".bak"))
        
    yield
    
    # Restore files
    if COMPLIANCE_YAML.with_suffix(".bak").exists():
        shutil.move(COMPLIANCE_YAML.with_suffix(".bak"), COMPLIANCE_YAML)
    if MANIFEST_JSON.with_suffix(".bak").exists():
        shutil.move(MANIFEST_JSON.with_suffix(".bak"), MANIFEST_JSON)

def test_startup_fails_on_hash_mismatch():
    """
    Test that modifying the YAML without updating the manifest raises a RuntimeError.
    """
    # 1. First ensure it loads fine initially
    ruleset, ruleset_hash = load_and_validate_compliance()
    assert ruleset is not None
    
    # 2. Tamper with the YAML file
    with open(COMPLIANCE_YAML, "r") as f:
        data = yaml.safe_load(f)
    
    # Modify a rule
    data["rules"]["max_claim_review_days"] = 999
    
    with open(COMPLIANCE_YAML, "w") as f:
        yaml.safe_dump(data, f)
        
    # 3. Try to load again, it should fail
    with pytest.raises(RuntimeError, match="CRITICAL: Compliance ruleset content changed"):
        load_and_validate_compliance()

def test_compliance_history_accumulates():
    """
    Test that every successful load logs a record to ComplianceHistoryRecord.
    """
    with SessionLocal() as db:
        initial_count = db.query(ComplianceHistoryRecord).count()
        
    load_and_validate_compliance()
    load_and_validate_compliance()
    load_and_validate_compliance()
    
    with SessionLocal() as db:
        final_count = db.query(ComplianceHistoryRecord).count()
        assert final_count == initial_count + 3
        
        # Verify fields of latest record
        latest = db.query(ComplianceHistoryRecord).order_by(ComplianceHistoryRecord.timestamp.desc()).first()
        assert latest.version_label == "1.0.0"
        assert latest.ruleset_hash is not None
        assert latest.loaded_by is not None
