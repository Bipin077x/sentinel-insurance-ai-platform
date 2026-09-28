import json
import yaml
import getpass
from pathlib import Path
from typing import Dict, Any, Tuple
from datetime import datetime, timezone
from core.canonical import compute_canonical_hash
from core.database import SessionLocal, ComplianceHistoryRecord
import uuid

COMPLIANCE_DIR = Path(__file__).parent.parent / "compliance"
COMPLIANCE_YAML = COMPLIANCE_DIR / "compliance_rules.yaml"
MANIFEST_JSON = COMPLIANCE_DIR / "manifest.json"

def load_and_validate_compliance() -> Tuple[Dict[str, Any], str]:
    """
    Loads compliance YAML, validates its hash against the manifest,
    logs it to the history table, and returns the ruleset and its hash.
    """
    if not COMPLIANCE_YAML.exists():
        raise FileNotFoundError(f"Compliance file not found: {COMPLIANCE_YAML}")
        
    if not MANIFEST_JSON.exists():
        raise FileNotFoundError(f"Compliance manifest not found: {MANIFEST_JSON}")

    # 1. Load the YAML
    with open(COMPLIANCE_YAML, "r") as f:
        ruleset = yaml.safe_load(f)
        
    # 2. Compute canonical hash
    ruleset_hash = compute_canonical_hash(ruleset)
    
    # 3. Read claimed version
    version_label = ruleset.get("version", "unknown")
    
    # 4. Validate against manifest
    with open(MANIFEST_JSON, "r") as f:
        manifest = json.load(f)
        
    expected_hash = manifest.get(version_label)
    
    if not expected_hash:
        raise RuntimeError(
            f"Compliance version '{version_label}' not found in {MANIFEST_JSON}. "
            "Please update the manifest when rolling out a new compliance version."
        )
        
    if ruleset_hash != expected_hash:
        raise RuntimeError(
            f"CRITICAL: Compliance ruleset content changed without a version bump! "
            f"Version '{version_label}' expects hash '{expected_hash}', but actual hash is '{ruleset_hash}'. "
            "Update the manifest or revert the file."
        )
        
    # 5. Log to history table
    with SessionLocal() as db:
        # Check if we already logged this exact version+hash combo recently to avoid spam, 
        # but the prompt says "every time the ruleset is loaded at startup"
        record = ComplianceHistoryRecord(
            id=f"comp_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            ruleset_hash=ruleset_hash,
            version_label=version_label,
            loaded_by=getpass.getuser()
        )
        db.add(record)
        db.commit()
        
    return ruleset, ruleset_hash
