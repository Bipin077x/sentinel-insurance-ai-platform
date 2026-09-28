import os
import argparse
from datetime import datetime, timezone
from sqlalchemy import select
from core.database import SessionLocal, DecisionRecord, AuditTrailRecord
from reporting.utils import save_and_log_report

def generate_escalation_report(pipeline: str, since: str = None) -> str:
    """
    Generates an aggregate report on escalated cases, their mechanisms, and triggering values.
    """
    now_ts = datetime.now(timezone.utc).isoformat()
    
    with SessionLocal() as db:
        query = db.query(DecisionRecord, AuditTrailRecord).join(
            AuditTrailRecord, DecisionRecord.id == AuditTrailRecord.decision_id
        )
        
        if pipeline != "all":
            query = query.filter(DecisionRecord.function_type == pipeline)
            
        if since:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(DecisionRecord.timestamp >= since_dt)
            
        records = query.all()
        
    total_decisions = len(records)
    if total_decisions == 0:
        return f"# Escalation Report ({pipeline})\n\nNo decisions found in the specified range."
        
    auto_decided = sum(1 for d, a in records if d.status.value == "auto_decided")
    escalated = sum(1 for d, a in records if d.status.value == "pending_review")
    
    # Mechanism counts
    mechanisms = {
        "fraud_override": [],
        "referral_override": [],
        "calibration_disagreement": [],
        "fabrication_failure": [],
        "extraction_validation_failure": [],
        "amount_ceiling": [],
        "other": []
    }
    
    fraud_scores = []
    referral_scores = []
    
    import re

    for d, a in records:
        if d.status.value != "pending_review":
            continue

        # Primary source: override_reason, set at decision-creation time by gate.py.
        # Populated for all decisions created after the Phase 8 structural fix.
        # Fallback: pattern-match against reasoning_text for legacy records where
        # override_reason is None (decisions created before this fix was applied).
        if a.override_reason is not None:
            reason = a.override_reason
            source = "structured"
        else:
            reason = d.reasoning_text
            source = "legacy_text_match"

        if "fraud_override" in reason:
            mechanisms["fraud_override"].append((d.id, source))
            match = re.search(r"fraud_score\s+([0-9\.]+)", reason)
            if match:
                fraud_scores.append(float(match.group(1)))
        elif "referral_override" in reason:
            mechanisms["referral_override"].append((d.id, source))
            match = re.search(r"referral_score\s+([0-9\.]+)", reason)
            if match:
                referral_scores.append(float(match.group(1)))
        elif "amount_ceiling" in reason:
            # gate.py hard ceiling: fires before fraud/referral/confidence checks.
            mechanisms["amount_ceiling"].append((d.id, source))
        elif "low_calibration_confidence" in reason or "calibration" in reason.lower():
            mechanisms["calibration_disagreement"].append((d.id, source))
        elif "Fabrication detected" in reason or "Coherence failure" in reason or "FABRICATION DETECTED" in reason:
            mechanisms["fabrication_failure"].append((d.id, source))
        elif "hallucination/sanity failure" in reason:
            # Extraction-layer sanity failures. Distinct from the gate-layer amount_ceiling.
            mechanisms["extraction_validation_failure"].append((d.id, source))
        else:
            mechanisms["other"].append((d.id, source))

    md = f"# Aggregate Escalation Report\n\n"
    md += f"**Pipeline:** {pipeline}\n"
    md += f"**Since:** {since if since else 'All time'}\n"
    md += f"**Generated At:** {now_ts}\n\n"
    
    md += f"## 1. Top-Level Summary\n"
    md += f"- **Total Decisions:** {total_decisions}\n"
    md += f"- **Auto-Decided:** {auto_decided} ({(auto_decided/total_decisions)*100:.1f}%)\n"
    md += f"- **Escalated (Pending Review):** {escalated} ({(escalated/total_decisions)*100:.1f}%)\n\n"
    
    if escalated > 0:
        md += f"## 2. Escalations by Mechanism\n"
        legacy_cases = []
        for mech, case_tuples in mechanisms.items():
            count = len(case_tuples)
            if count > 0:
                md += f"- **{mech}:** {count} ({(count/escalated)*100:.1f}%)\n"
                for cid, source in case_tuples:
                    src_label = "" if source == "structured" else " ⚠ legacy-text-match"
                    md += f"  - `{cid}`{src_label}\n"
                    if source != "structured":
                        legacy_cases.append(cid)
        if legacy_cases:
            md += f"\n> **Note:** Cases marked ⚠ used legacy text-match fallback against `reasoning_text` "
            md += f"(override_reason was None — these decisions predate the Phase 8 structured-field fix). "
            md += f"Re-running the affected pipelines will populate the structured field for future runs.\n"
                
        md += "\n## 3. Deterministic Override Distributions\n"
        
        if fraud_scores:
            md += "### Fraud Scores triggering Escalation\n"
            buckets = {}
            for s in fraud_scores:
                b = round(s, 1)
                buckets[b] = buckets.get(b, 0) + 1
            for b, c in sorted(buckets.items()):
                md += f"- `{b}`: {'#' * c} ({c})\n"
                
        if referral_scores:
            md += "\n### Referral Scores triggering Escalation\n"
            buckets = {}
            for s in referral_scores:
                b = round(s, 1)
                buckets[b] = buckets.get(b, 0) + 1
            for b, c in sorted(buckets.items()):
                md += f"- `{b}`: {'#' * c} ({c})\n"
                
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate aggregate escalation report.")
    parser.add_argument("--pipeline", required=True, help="claims | underwriting | brokerage | all")
    parser.add_argument("--since", required=False, help="ISO format date string")
    args = parser.parse_args()
    
    report_md = generate_escalation_report(args.pipeline, args.since)
    
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"escalation_{args.pipeline}_{ts_str}.md"
    
    saved_path = save_and_log_report(
        report_content=report_md, 
        report_type="escalation", 
        filters={"pipeline": args.pipeline, "since": args.since}, 
        filename=filename
    )
    
    print(f"Report successfully generated and logged: {saved_path}")
