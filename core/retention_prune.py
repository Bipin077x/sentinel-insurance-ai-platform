import uuid
from datetime import datetime
import hashlib
import json
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.database import SessionLocal, RawDocumentRecord, DeletionLogRecord, init_db
from core.retention_policy import load_retention_policy

def prune_expired_documents():
    db: Session = SessionLocal()
    
    # Load retention policy
    policy, policy_hash = load_retention_policy()
    
    now = datetime.utcnow()
    
    # Find expired raw documents
    expired_docs = db.query(RawDocumentRecord).filter(RawDocumentRecord.retention_expiry <= now).all()
    
    deleted_count = 0
    for doc in expired_docs:
        decision_id = doc.decision_id
        
        # Determine the prev_record_hash for deletion_logs chain
        prev_log = db.execute(
            select(DeletionLogRecord).order_by(DeletionLogRecord.timestamp.desc())
        ).scalars().first()
        prev_hash = prev_log.record_hash if prev_log else "genesis"
        
        log_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Calculate WORM hash
        content = f"{log_id}:{decision_id}:{policy_hash}:{timestamp.isoformat()}:{prev_hash}"
        record_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        # Add deletion log (No PII)
        del_log = DeletionLogRecord(
            id=log_id,
            decision_id=decision_id,
            policy_version_hash=policy_hash,
            timestamp=timestamp,
            record_hash=record_hash,
            prev_record_hash=prev_hash
        )
        
        db.add(del_log)
        db.delete(doc) # Hard delete the PII record
        
        # Commit per record or all at once? Let's commit per record so if one fails, others succeed
        db.commit()
        deleted_count += 1
        
    db.close()
    return deleted_count, policy_hash

if __name__ == "__main__":
    init_db()
    count, hash_val = prune_expired_documents()
    print(f"Deleted {count} expired raw documents using policy hash {hash_val}.")
