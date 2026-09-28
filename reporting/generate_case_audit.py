import sys
import json
import argparse
from core.reasoning_log import get_decision_trail
from core.chain_verify import verify_single_decision
from reporting.utils import save_and_log_report
from datetime import datetime, timezone

def generate_case_audit(decision_id: str) -> str:
    trail = get_decision_trail(decision_id)
    if not trail:
        print(f"Error: Decision {decision_id} not found in database.", file=sys.stderr)
        sys.exit(1)
        
    decision = trail["decision"]
    audit = trail["audit_trail"]
    
    # 1. Live Integrity Check
    try:
        is_intact = verify_single_decision(decision_id)
        integrity_status = "PASSED" if is_intact else "FAILED"
    except Exception as e:
        integrity_status = f"FAILED: {e}"

    # Check if raw document still exists
    from core.database import SessionLocal, RawDocumentRecord
    with SessionLocal() as db:
        raw_doc = db.query(RawDocumentRecord).filter(RawDocumentRecord.decision_id == decision_id).first()
        if raw_doc:
            retention_status = "The raw, unredacted data is currently stored securely in the `raw_documents` table."
        else:
            retention_status = "**The raw, unredacted data has been PERMANENTLY DELETED per the configured retention policy.**"
            
    now_ts = datetime.now(timezone.utc).isoformat()
    # Format the report
    md = f"# Case Audit Report: {decision_id}\n\n"
    md += f"**Subject ID:** {decision.subject_id}\n"
    md += f"**Function Type:** {decision.function_type.value}\n"
    md += f"**Final Outcome:** {decision.outcome}\n"
    md += f"**Status:** {decision.status.value}\n\n"
    
    md += f"## 1. Input Data & Redaction\n"
    md += f"```json\n{json.dumps(audit.inputs_snapshot, indent=2)}\n```\n"
    md += f"> **Note:** Redacted values (e.g., names, SSNs) appear as `[REDACTED]`. {retention_status}\n\n"
    
    md += f"## 2. Rule Evaluation\n"
    md += f"```json\n{json.dumps(audit.rule_results, indent=2)}\n```\n\n"
    
    md += f"## 3. Escalation & Overrides\n"
    if audit.override_reason:
        md += f"**Override Mechanism Fired:** `{audit.override_reason}`\n\n"
    else:
        md += "**Override Mechanism Fired:** None\n\n"
        
    md += f"## 4. Model Confidence & Calibration\n"
    md += f"**Confidence Score:** {decision.confidence_score}\n"
    md += f"**Confidence Source:** `{decision.confidence_source}`\n"
    md += "> **Note:** This confidence score represents semantic self-consistency across multiple sampled generations, not an absolute probability of correctness.\n\n"
    
    md += f"## 5. Reasoning & Faithfulness\n"
    md += f"**Reasoning Text:**\n> {decision.reasoning_text}\n\n"
    if "Fabrication detected" in decision.reasoning_text or "Coherence failure" in decision.reasoning_text:
        md += "**Faithfulness Check:** [FAILED] (See reasoning text for details)\n\n"
    else:
        md += "**Faithfulness Check:** [PASSED]\n\n"
        
    md += f"## 6. Cryptographic Integrity (Live Verification)\n"
    md += f"**Verification Timestamp:** {now_ts}\n"
    md += f"**Chain Verification Status:** {integrity_status}\n"
    md += f"**Model Version Pinned:** {decision.model_version}\n"
    md += f"**Compliance Ruleset Hash Active:** {decision.compliance_ruleset_hash}\n"
    if decision.prompt_hash:
        md += f"**Prompt Hash Active:** {decision.prompt_hash}\n"
        
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an individual case audit report.")
    parser.add_argument("decision_id", help="The decision ID to audit (e.g. dec_CLIENT-1008)")
    args = parser.parse_args()
    
    report_md = generate_case_audit(args.decision_id)
    filename = f"audit_{args.decision_id}.md"
    
    saved_path = save_and_log_report(
        report_content=report_md, 
        report_type="case_audit", 
        filters={"decision_id": args.decision_id}, 
        filename=filename
    )
    
    print(f"Report successfully generated and logged: {saved_path}")
