import os
import argparse
from datetime import datetime, timezone
from sqlalchemy import select
from core.database import SessionLocal, DecisionRecord, AuditTrailRecord
from reporting.utils import save_and_log_report

def generate_fabrication_log(pipeline: str, since: str = None) -> str:
    """
    Generates a list of all fabrication/coherence failure incidents caught by faithfulness.py.
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
        return f"# Fabrication / Faithfulness Incident Log\n\nNo decisions found in the specified range."
        
    incidents = []
    
    for d, a in records:
        reason = d.reasoning_text
        if "Fabrication detected" in reason or "Coherence failure" in reason:
            # Determine if this is a synthetic test or real incident
            # (In this POC, all data is synthetic, but we look for test IDs like 'fake', 'bad', 'bypass', 'tamper')
            is_synthetic_test = False
            if "fake" in d.subject_id.lower() or "bad" in d.subject_id.lower() or "bypass" in d.subject_id.lower() or "test" in d.subject_id.lower():
                is_synthetic_test = True
                
            incidents.append({
                "decision_id": d.id,
                "subject_id": d.subject_id,
                "function_type": d.function_type.value,
                "timestamp": d.timestamp.isoformat(),
                "reasoning_text": d.reasoning_text,
                "outcome": d.outcome,
                "status": d.status.value,
                "is_synthetic_test": is_synthetic_test
            })

    md = f"# Fabrication / Faithfulness Incident Log\n\n"
    md += f"**Pipeline:** {pipeline}\n"
    md += f"**Since:** {since if since else 'All time'}\n"
    md += f"**Generated At:** {now_ts}\n\n"
    
    md += f"## 1. Aggregate Incident Rate\n"
    md += f"- **Total Decisions Analyzed:** {total_decisions}\n"
    md += f"- **Total Incidents Caught:** {len(incidents)} ({(len(incidents)/total_decisions)*100:.2f}%)\n\n"
    
    if incidents:
        md += f"## 2. Incident Details\n\n"
        for idx, inc in enumerate(incidents):
            md += f"### Incident {idx+1}: {inc['decision_id']} ({inc['function_type']})\n"
            if inc["is_synthetic_test"]:
                md += f"> **TEST RECORD**: This incident was triggered by an adversarial test fixture (`{inc['subject_id']}`), not a real pipeline run.\n\n"
            
            md += f"- **Timestamp:** {inc['timestamp']}\n"
            md += f"- **Subject ID:** {inc['subject_id']}\n"
            md += f"- **Resulting Status:** {inc['status']}\n"
            md += f"- **Recorded Outcome:** {inc['outcome']}\n"
            md += f"- **Flag Detail:**\n"
            md += f"```text\n{inc['reasoning_text']}\n```\n\n"
            
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fabrication/coherence log.")
    parser.add_argument("--pipeline", required=True, help="claims | underwriting | brokerage | all")
    parser.add_argument("--since", required=False, help="ISO format date string")
    args = parser.parse_args()
    
    report_md = generate_fabrication_log(args.pipeline, args.since)
    
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fabrication_{args.pipeline}_{ts_str}.md"
    
    saved_path = save_and_log_report(
        report_content=report_md, 
        report_type="fabrication_log", 
        filters={"pipeline": args.pipeline, "since": args.since}, 
        filename=filename
    )
    
    print(f"Report successfully generated and logged: {saved_path}")
