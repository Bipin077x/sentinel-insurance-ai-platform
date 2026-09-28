"""
audit/inject_anomalies.py — Test fixture injector for Phase 5.

Injects 5 carefully crafted decisions designed to exercise each anomaly detector.
Run ONCE before running run_audit.py for testing. The WORM constraint means these
records persist permanently once written.

Fixtures injected:
  1. ANOMALY_FIXTURE_LARGE_CLM     — amount=$150,000 (10× peer mean) → amount_outlier
  2. ANOMALY_FIXTURE_CLUSTER_{1-5} — confidence=0.851 cluster just above 0.85 → threshold_clustering
  3. ANOMALY_FIXTURE_TIMING_{1-4}  — 4 decisions from same subject within seconds → timing_anomaly
  4. ANOMALY_FIXTURE_DUP_{A,B}     — same policy/type/amount bucket → near_duplicate
  5. ANOMALY_FIXTURE_LEGIT_LARGE   — $85,000 but all rules passed (negative case) → amount_outlier
                                     LLM review should return "dismiss_benign"
"""

import json
import hashlib
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision
from core.database import SessionLocal, DecisionRecord
from core.compliance import get_active_compliance_ruleset_hash


def _already_exists(decision_id: str) -> bool:
    with SessionLocal() as db:
        return db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first() is not None


def _log(decision: Decision, audit: AuditTrailEntry, label: str):
    if _already_exists(decision.id):
        print(f"  [SKIP] {decision.id} already exists.")
        return
    log_decision(decision, audit)
    print(f"  [OK]   {decision.id} — {label}")


def inject_all():
    comp_hash = get_active_compliance_ruleset_hash()
    now = datetime.now(timezone.utc)

    print("Injecting Phase 5 anomaly test fixtures...")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Fixture 1: Amount outlier ($150,000 claim — ~10× peer average)
    # -------------------------------------------------------------------------
    fid = "dec_ANOMALY_FIXTURE_LARGE_CLM"
    amount_large = 150_000.0
    snap1 = {
        "claim": {
            "id": "CLM-ANOMALY-LARGE-001",
            "policy_id": "POL-ANOMALY-001",
            "date_filed": now.isoformat(),
            "incident_date": (now - timedelta(days=3)).isoformat(),
            "claim_type": "medical",
            "amount": amount_large,
            "cause": "Emergency surgery",
            "evidence_list": ["hospital_bill.pdf"],
        },
        "fraud_score": 0.05,
        "fraud_flags": [],
        "llm_self_reported_confidence": 0.95,
    }
    d1 = Decision(
        id=fid,
        function_type=FunctionType.CLAIMS,
        subject_id="CLM-ANOMALY-LARGE-001",
        outcome="approve",
        confidence_score=0.95,
        confidence_source="semantic_consistency_n5",
        rules_fired=[],
        reasoning_text="Large medical claim. All rules passed. Approved.",
        model_version="mock-llm-1.0",
        timestamp=now,
        status=DecisionStatus.AUTO_DECIDED,
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test_prompt_hash_anomaly",
    )
    a1 = AuditTrailEntry(
        decision_id=fid,
        inputs_hash=hashlib.sha256(json.dumps(snap1, sort_keys=True, default=str).encode()).hexdigest(),
        inputs_snapshot=snap1,
        rule_results={"policy_active": True, "coverage_check": True, "evidence_submitted": True},
        model_prompt_version="v1",
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test_prompt_hash_anomaly",
        override_reason=None,
    )
    _log(d1, a1, f"Amount outlier: ${amount_large:,.0f}")

    # -------------------------------------------------------------------------
    # Fixture 2: Legitimate large claim (NEGATIVE CASE — should be dismissed as benign)
    # All rules passed, subject_id contains "LEGIT" → mock LLM returns dismiss_benign
    # -------------------------------------------------------------------------
    fid2 = "dec_ANOMALY_FIXTURE_LEGIT_LARGE_2"
    amount_legit = 120_000.0
    snap2 = {
        "claim": {
            "id": "CLM-ANOMALY-LEGIT-002",
            "policy_id": "POL-CORP-TRAVEL-001",
            "date_filed": now.isoformat(),
            "incident_date": (now - timedelta(days=10)).isoformat(),
            "claim_type": "medical_evacuation",
            "amount": amount_legit,
            "cause": "Emergency medical evacuation from remote area",
            "evidence_list": [
                "air_ambulance_invoice.pdf",
                "hospital_admission.pdf",
                "doctors_report.pdf",
                "travel_policy_confirmation.pdf",
                "independent_medical_assessment.pdf",
            ],
        },
        "fraud_score": 0.01,
        "fraud_flags": [],
        "llm_self_reported_confidence": 0.98,
    }
    d2 = Decision(
        id=fid2,
        function_type=FunctionType.CLAIMS,
        subject_id="CLM-ANOMALY-LEGIT-002",
        outcome="approve",
        confidence_score=0.98,
        confidence_source="semantic_consistency_n5",
        rules_fired=[],
        reasoning_text=(
            "Medical evacuation claim. Five independent documents provided including "
            "air ambulance invoice and independent medical assessment. "
            "All rules passed. Approved with high confidence."
        ),
        model_version="mock-llm-1.0",
        timestamp=now,
        status=DecisionStatus.AUTO_DECIDED,
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test_prompt_hash_anomaly",
    )
    a2 = AuditTrailEntry(
        decision_id=fid2,
        inputs_hash=hashlib.sha256(json.dumps(snap2, sort_keys=True, default=str).encode()).hexdigest(),
        inputs_snapshot=snap2,
        rule_results={
            "policy_active":              True,
            "coverage_check":             True,
            "evidence_submitted":         True,
            "independent_assessment":     True,
            "evacuation_coverage_active": True,
        },
        model_prompt_version="v1",
        compliance_ruleset_hash=comp_hash,
        prompt_hash="test_prompt_hash_anomaly",
        override_reason=None,
    )
    _log(d2, a2, f"Legit large claim (negative case): ${amount_legit:,.0f}, 5 docs, all rules passed")

    # -------------------------------------------------------------------------
    # Fixture 3: Threshold clustering — 5 decisions with confidence=0.851
    # Just above the 0.85 claims threshold.
    # -------------------------------------------------------------------------
    print()
    cluster_base_ts = now - timedelta(hours=2)
    for idx in range(1, 6):
        fid3 = f"dec_ANOMALY_FIXTURE_CLUSTER_{idx:03d}"
        snap3 = {
            "claim": {
                "id": f"CLM-CLUSTER-{idx:03d}",
                "policy_id": f"POL-CLUSTER-{idx:03d}",
                "date_filed": (cluster_base_ts + timedelta(minutes=idx*5)).isoformat(),
                "incident_date": (cluster_base_ts - timedelta(days=1)).isoformat(),
                "claim_type": "baggage_loss",
                "amount": 800.0 + idx * 10,
                "cause": "Lost baggage",
                "evidence_list": ["baggage_report.pdf"],
            },
            "fraud_score": 0.20,
            "fraud_flags": ["borderline_fraud_score"],
            "llm_self_reported_confidence": 0.851,
        }
        d3 = Decision(
            id=fid3,
            function_type=FunctionType.CLAIMS,
            subject_id=f"CLM-CLUSTER-{idx:03d}",
            outcome="approve",
            confidence_score=0.851,
            confidence_source="semantic_consistency_n5",
            rules_fired=[],
            reasoning_text="Borderline confidence. Approved at threshold.",
            model_version="mock-llm-1.0",
            timestamp=cluster_base_ts + timedelta(minutes=idx*5),
            status=DecisionStatus.AUTO_DECIDED,
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
        )
        a3 = AuditTrailEntry(
            decision_id=fid3,
            inputs_hash=hashlib.sha256(json.dumps(snap3, sort_keys=True, default=str).encode()).hexdigest(),
            inputs_snapshot=snap3,
            rule_results={"policy_active": True, "coverage_check": True},
            model_prompt_version="v1",
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
            override_reason=None,
        )
        _log(d3, a3, f"Threshold cluster #{idx}: confidence=0.851")

    # -------------------------------------------------------------------------
    # Fixture 4: Timing anomaly — 4 decisions from same subject within 5 minutes
    # -------------------------------------------------------------------------
    print()
    fraud_ring_ts = now - timedelta(hours=1)
    for idx in range(1, 5):
        fid4 = f"dec_ANOMALY_FIXTURE_TIMING_{idx:03d}"
        snap4 = {
            "claim": {
                "id": f"CLM-FRAUD-RING-{idx:03d}",
                "policy_id": f"POL-FRAUD-{idx:03d}",
                "date_filed": (fraud_ring_ts + timedelta(minutes=idx)).isoformat(),
                "incident_date": (fraud_ring_ts - timedelta(days=2)).isoformat(),
                "claim_type": "travel_cancellation",
                "amount": 1200.0 + idx * 50,
                "cause": "Trip cancellation",
                "evidence_list": ["cancellation_notice.pdf"],
            },
            "fraud_score": 0.35,
            "fraud_flags": [],
            "llm_self_reported_confidence": 0.90,
        }
        d4 = Decision(
            id=fid4,
            function_type=FunctionType.CLAIMS,
            subject_id="CLM-FRAUD-RING-001",   # SAME subject_id for all 4
            outcome="approve",
            confidence_score=0.90,
            confidence_source="semantic_consistency_n5",
            rules_fired=[],
            reasoning_text="Travel cancellation claim approved.",
            model_version="mock-llm-1.0",
            timestamp=fraud_ring_ts + timedelta(minutes=idx),
            status=DecisionStatus.AUTO_DECIDED,
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
        )
        a4 = AuditTrailEntry(
            decision_id=fid4,
            inputs_hash=hashlib.sha256(json.dumps(snap4, sort_keys=True, default=str).encode()).hexdigest(),
            inputs_snapshot=snap4,
            rule_results={"policy_active": True, "coverage_check": True},
            model_prompt_version="v1",
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
            override_reason=None,
        )
        _log(d4, a4, f"Timing cluster #{idx}: subject=CLM-FRAUD-RING-001, t+{idx}min")

    # -------------------------------------------------------------------------
    # Fixture 5: Near-duplicate pair — same policy, same type, amount within $100 bucket
    # -------------------------------------------------------------------------
    print()
    for suffix, amount_val in [("A", 2500.0), ("B", 2530.0)]:
        fid5 = f"dec_ANOMALY_FIXTURE_DUP_{suffix}"
        snap5 = {
            "claim": {
                "id": f"CLM-DUP-{suffix}",
                "policy_id": "POL-DUP-POLICY-999",   # SAME policy
                "date_filed": now.isoformat(),
                "incident_date": (now - timedelta(days=5)).isoformat(),
                "claim_type": "medical",              # SAME type
                "amount": amount_val,                 # Both round to $2500
                "cause": "Medical expenses",
                "evidence_list": ["medical_receipt.pdf"],
            },
            "fraud_score": 0.10,
            "fraud_flags": [],
            "llm_self_reported_confidence": 0.92,
        }
        d5 = Decision(
            id=fid5,
            function_type=FunctionType.CLAIMS,
            subject_id=f"CLM-DUP-{suffix}",
            outcome="approve",
            confidence_score=0.92,
            confidence_source="semantic_consistency_n5",
            rules_fired=[],
            reasoning_text="Medical claim approved.",
            model_version="mock-llm-1.0",
            timestamp=now + timedelta(seconds=10 if suffix == "B" else 0),
            status=DecisionStatus.AUTO_DECIDED,
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
        )
        a5 = AuditTrailEntry(
            decision_id=fid5,
            inputs_hash=hashlib.sha256(json.dumps(snap5, sort_keys=True, default=str).encode()).hexdigest(),
            inputs_snapshot=snap5,
            rule_results={"policy_active": True, "coverage_check": True},
            model_prompt_version="v1",
            compliance_ruleset_hash=comp_hash,
            prompt_hash="test_prompt_hash_anomaly",
            override_reason=None,
        )
        _log(d5, a5, f"Near-duplicate {suffix}: POL-DUP-POLICY-999/medical/${amount_val:,.0f}")

    print("\n" + "=" * 60)
    print("Fixture injection complete.")
    print("Run: venv\\Scripts\\python.exe -m audit.run_audit")


if __name__ == "__main__":
    inject_all()
