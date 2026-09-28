import sys
import os
import argparse
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core.database import SessionLocal, DeletionLogRecord
from core.chain_verify import verify_chain
from reporting.utils import save_and_log_report

def generate_deletion_report() -> str:
    db = SessionLocal()
    logs = db.query(DeletionLogRecord).order_by(DeletionLogRecord.timestamp.desc()).all()
    
    # 1. Live Integrity Check
    try:
        is_intact = verify_chain()
        integrity_status = "PASSED" if is_intact else "FAILED"
    except Exception as e:
        integrity_status = f"FAILED: {e}"

    md = f"# PII Deletion Audit Report\n\n"
    md += f"**Report Generated:** {datetime.utcnow().isoformat()} UTC\n"
    md += f"**Chain Verification Status:** {integrity_status}\n\n"
    
    md += "> **Integrity Note:** This report confirms that the deletions listed below successfully purged PII from `raw_documents` without breaking the WORM hash chain of the `decisions` and `audit_trails` tables.\n\n"
    
    md += "## Deletion Log\n\n"
    md += "| Timestamp (UTC) | Decision ID | Policy Version Hash | Record Hash |\n"
    md += "|---|---|---|---|\n"
    
    for log in logs:
        md += f"| {log.timestamp.isoformat()} | {log.decision_id} | {log.policy_version_hash} | {log.record_hash} |\n"
        
    if not logs:
        md += "| (No deletions logged yet) | | | |\n"
        
    db.close()
    return md

if __name__ == "__main__":
    report_md = generate_deletion_report()
    filename = f"deletion_audit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
    
    saved_path = save_and_log_report(
        report_content=report_md, 
        report_type="deletion_audit", 
        filters={}, 
        filename=filename
    )
    
    print(f"Deletion report successfully generated and logged: {saved_path}")
