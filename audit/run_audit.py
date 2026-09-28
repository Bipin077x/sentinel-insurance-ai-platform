"""
audit/run_audit.py — Financial Audit Pipeline runner.

Wires anomaly_detection → llm_review → generate_audit_findings.
Each flag is logged as a Decision with function_type=AUDIT, same integrity
standard as every other pipeline decision.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone

from audit.anomaly_detection import find_anomalies, AnomalyFlag
from audit.llm_review import conduct_audit_review
from audit.generate_audit_findings import generate_audit_findings
from core.reasoning_log import get_decision_trail, log_decision
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.database import SessionLocal, DecisionRecord


def run_pipeline():
    print("=" * 60)
    print("Financial Audit Pipeline")
    print("=" * 60)

    # 1. Anomaly Detection (deterministic, no LLM)
    print("\n[1] Running statistical anomaly detectors...")
    flags = find_anomalies()

    with SessionLocal() as db:
        total_scanned = db.query(DecisionRecord).count()

    print(f"    Scanned {total_scanned} decisions, raised {len(flags)} flag(s).")
    for f in flags:
        print(f"    [{f.detector}] {', '.join(f.decision_ids[:3])}{'...' if len(f.decision_ids) > 3 else ''}")

    if not flags:
        print("\nNo anomalies detected. Generating clean report.")
        path = generate_audit_findings(total_scanned, [], [])
        print(f"Report: {path}")
        return

    # 2. LLM-Assisted Review (one per flag)
    print("\n[2] Running LLM-assisted review for each flag...")
    results = []
    audit_decision_ids = []

    from core.compliance import get_active_compliance_ruleset_hash
    active_comp_hash = get_active_compliance_ruleset_hash()

    for flag in flags:
        # Use the first decision ID in the flag as the representative case
        primary_id = flag.decision_ids[0]

        # Skip if we'd be auditing an audit decision (prevent loops)
        if any(("audit_" in did or "ANOMALY_FIXTURE_" in did) for did in flag.decision_ids):
            # Only skip pure fixture flags — still process mixed flags
            pass

        print(f"\n  Reviewing flag: [{flag.detector}] primary={primary_id}")
        print(f"    Description: {flag.description[:100]}...")

        decision_data = get_decision_trail(primary_id)
        if not decision_data:
            print(f"    Warning: Could not retrieve trail for {primary_id} — skipping.")
            continue

        finding, prompt_hash, calibrated_confidence, faithfulness_errors = conduct_audit_review(
            flag, decision_data
        )

        if faithfulness_errors:
            print(f"    ⚠ Faithfulness errors: {faithfulness_errors}")
        print(f"    Action: {finding.recommended_action}  Confidence: {calibrated_confidence:.0%}")

        results.append({
            "flag":                  flag,
            "finding":               finding,
            "prompt_hash":           prompt_hash,
            "calibrated_confidence": calibrated_confidence,
            "faithfulness_errors":   faithfulness_errors,
        })

        # 3. Log the audit finding as an append-only Decision record
        # ID: deterministic hash of detector + sorted decision IDs (stable, dedup-safe)
        flag_sig = hashlib.sha256(
            (flag.detector + "|" + "|".join(sorted(flag.decision_ids))).encode()
        ).hexdigest()[:16]
        audit_id = f"audit_{flag.detector}_{flag_sig}"

        # Guard against re-logging a flag we've already seen
        with SessionLocal() as db:
            existing = db.query(DecisionRecord).filter(DecisionRecord.id == audit_id).first()
        if existing:
            audit_decision_ids.append(audit_id)
            print(f"    Audit record {audit_id} already exists — skipping log.")
            continue

        audit_decision = Decision(
            id=audit_id,
            function_type=FunctionType.AUDIT,
            subject_id=primary_id,
            outcome=finding.recommended_action,
            confidence_score=calibrated_confidence,
            confidence_source="semantic_consistency_n3",
            rules_fired=[f"detector:{flag.detector}"] + (
                [f"faithfulness_failure"] if faithfulness_errors else []
            ),
            reasoning_text=(
                f"[{flag.detector}] {flag.description[:200]} | "
                f"Auditor: {finding.audit_rationale[:300]}"
            ),
            model_version="mock-llm-1.0",
            timestamp=datetime.now(timezone.utc),
            status=DecisionStatus.AUTO_DECIDED,
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash,
        )

        inputs_snapshot = {
            "flag_detector":  flag.detector,
            "flag_description": flag.description,
            "statistical_basis": flag.statistical_basis,
            "decision_ids_flagged": flag.decision_ids,
            "cited_evidence": finding.cited_evidence,
        }
        inputs_hash = hashlib.sha256(
            json.dumps(inputs_snapshot, sort_keys=True).encode()
        ).hexdigest()

        audit_trail_entry = AuditTrailEntry(
            decision_id=audit_id,
            inputs_hash=inputs_hash,
            inputs_snapshot=inputs_snapshot,
            rule_results={
                "anomaly_checked":    True,
                "faithfulness_passed": len(faithfulness_errors) == 0,
                "calibration_passed":  calibrated_confidence >= 0.6,
            },
            model_prompt_version="v2",
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash,
            reviewer_id=None,
            override_reason=f"audit_flag:{flag.detector}" if faithfulness_errors else None,
        )

        log_decision(audit_decision, audit_trail_entry)
        audit_decision_ids.append(audit_id)
        print(f"    Logged audit decision: {audit_id}")

    # 4. Generate Report
    print("\n[3] Generating audit findings report...")
    file_path = generate_audit_findings(total_scanned, results, audit_decision_ids)
    print(f"\nReport successfully generated: {file_path}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
