import os
import json
import hashlib
from datetime import datetime, timezone
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision
from core.compliance import get_active_compliance_ruleset_hash

def inject():
    comp_hash = get_active_compliance_ruleset_hash()
    now = datetime.now(timezone.utc)
    
    fid = "dec_PENDING_001"
    snap = {"claim": {"id": "PENDING_123", "amount": 5000.0}}
    
    d = Decision(
        id=fid,
        function_type=FunctionType.CLAIMS,
        subject_id="PENDING_123",
        outcome="approve",
        confidence_score=0.6,
        confidence_source="test",
        rules_fired=[],
        reasoning_text="Needs manual review.",
        model_version="mock-llm-1.0",
        timestamp=now,
        status=DecisionStatus.PENDING_REVIEW,
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test",
    )
    
    a = AuditTrailEntry(
        decision_id=fid,
        inputs_hash=hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest(),
        inputs_snapshot=snap,
        rule_results={},
        model_prompt_version="v1",
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test",
        override_reason=None,
    )
    
    log_decision(d, a)
    print("Injected PENDING_REVIEW decision")

if __name__ == "__main__":
    inject()
