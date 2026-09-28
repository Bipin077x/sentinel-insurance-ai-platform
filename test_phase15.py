import json
import uuid
from datetime import datetime, timedelta
import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.database import SessionLocal, RawDocumentRecord, DecisionRecord, AuditTrailRecord, DeletionLogRecord, init_db
from core.chain_verify import verify_chain
from core.retention_prune import prune_expired_documents
from reporting.generate_case_audit import generate_case_audit
from reporting.utils import save_and_log_report
from claims.run_claims import run_pipeline

def run_phase15_test():
    init_db()
    db = SessionLocal()
    
    print("--- 1. Baseline Test Setup ---")
    # Run the full pipeline to generate real records
    run_pipeline(use_adapters=False)
    
    # Grab the first raw_document we just generated
    raw_doc = db.query(RawDocumentRecord).first()
    if not raw_doc:
        print("Test failed: No raw document generated.")
        return
        
    decision = db.query(DecisionRecord).filter(DecisionRecord.id == raw_doc.decision_id).first()
    raw_doc_id = raw_doc.id
    
    if not raw_doc:
        print("Test failed: No raw document generated.")
        return

    print(f"Generated Case: {decision.id}")
    
    print("\n--- 2. Pre-Deletion Integrity Check ---")
    integrity_pre = verify_chain()
    print(f"Chain Verify PASS: {integrity_pre}")
    
    print("\n--- 3. Negative Test: Prune Before Expiry ---")
    deleted_count, _ = prune_expired_documents()
    print(f"Deleted count before expiry (should be 0): {deleted_count}")
    
    print("\n--- 4. Backdating Record & Pruning ---")
    # Using raw SQL to bypass SQLAlchemy ORM if needed, though raw_documents has no UPDATE trigger
    db.execute(
        text("UPDATE raw_documents SET retention_expiry = :past WHERE id = :doc_id"),
        {"past": (datetime.utcnow() - timedelta(days=1)).isoformat(), "doc_id": raw_doc.id}
    )
    db.commit()
    
    deleted_count, _ = prune_expired_documents()
    print(f"Deleted count after backdating (should be >= 1): {deleted_count}")
    
    print("\n--- 5. The Core Architectural Test: Post-Deletion Integrity Check ---")
    try:
        integrity_post = verify_chain()
        print(f"Chain Verify PASS: {integrity_post}")
        if integrity_post:
            print("  -> RESULT: Deleting raw_documents does NOT break decisions/audit_trails chain!")
    except Exception as e:
        print(f"Chain Verify FAILED: {e}")
        print("  -> RESULT: Deleting raw_documents broke the chain! Structural flaw detected.")
        
    print("\n--- 6. Generate Case Audit Report on Deleted Record ---")
    report_md = generate_case_audit(decision.id)
    report_file = save_and_log_report(report_md, "case_audit", {"decision_id": decision.id}, f"audit_{decision.id}.md")
    print(f"Audit report generated: {report_file}")
    with open(report_file, 'r') as f:
        report_content = f.read()
        if "John Doe" not in report_content and "000-00-0000" not in report_content:
            print("  -> Verified: PII is completely absent from the generated audit report.")
    
    print("\n--- 7. Query Deleted Content Directly ---")
    check_doc = db.query(RawDocumentRecord).filter(RawDocumentRecord.id == raw_doc_id).first()
    if check_doc is None:
        print("  -> Verified: Record is permanently hard-deleted from raw_documents.")
        
    print("\n--- 8. Verify Deletion Log ---")
    log = db.query(DeletionLogRecord).filter(DeletionLogRecord.decision_id == decision.id).first()
    if log:
        print(f"Deletion Log found: {log.id}")
        log_json = json.dumps({
            "id": log.id,
            "decision_id": log.decision_id,
            "policy_version_hash": log.policy_version_hash,
            "timestamp": log.timestamp.isoformat(),
            "record_hash": log.record_hash
        })
        if "John Doe" not in log_json and "000-00-0000" not in log_json:
            print("  -> Verified: Zero PII found in the deletion log.")
    
    db.close()

if __name__ == "__main__":
    run_phase15_test()
