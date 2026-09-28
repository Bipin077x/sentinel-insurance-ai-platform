import json
from core.database import SessionLocal, DecisionRecord, AuditTrailRecord
from core.canonical import compute_canonical_hash
from datetime import timezone

def verify_table_chain(table_class, records):
    if not records:
        print(f"[{table_class.__tablename__}] Table is empty.")
        return True
        
    expected_prev = None
    
    for i, record in enumerate(records):
        if table_class == DecisionRecord:
            from core.models import Decision
            # Reconstruct Pydantic model to match exact dump format used during insertion
            pydantic_obj = Decision(
                id=record.id,
                function_type=record.function_type,
                subject_id=record.subject_id,
                outcome=record.outcome,
                confidence_score=record.confidence_score,
                confidence_source=record.confidence_source,
                rules_fired=json.loads(record.rules_fired),
                reasoning_text=record.reasoning_text,
                model_version=record.model_version,
                timestamp=record.timestamp.replace(tzinfo=timezone.utc), # Add back UTC tz to match original insertion
                status=record.status,
                compliance_ruleset_hash=record.compliance_ruleset_hash,
                prompt_hash=record.prompt_hash,
                record_hash=None,
                prev_record_hash=record.prev_record_hash
            )
            record_dict = pydantic_obj.model_dump(mode='json', exclude={'record_hash'})
            
        elif table_class == AuditTrailRecord:
            from core.models import AuditTrailEntry
            pydantic_obj = AuditTrailEntry(
                decision_id=record.decision_id,
                inputs_hash=record.inputs_hash,
                inputs_snapshot=json.loads(record.inputs_snapshot),
                rule_results=json.loads(record.rule_results),
                model_prompt_version=record.model_prompt_version,
                compliance_ruleset_hash=record.compliance_ruleset_hash,
                prompt_hash=record.prompt_hash,
                reviewer_id=record.reviewer_id,
                override_reason=record.override_reason,
                record_hash=None,
                prev_record_hash=record.prev_record_hash
            )
            record_dict = pydantic_obj.model_dump(mode='json', exclude={'record_hash'})
            
        stored_hash = record.record_hash
        stored_prev = record.prev_record_hash
        
        # 1. Check prev_record_hash link
        if stored_prev != expected_prev:
            print(f"[{table_class.__tablename__}] CHAIN BROKEN at index {i} (ID: {getattr(record, 'id', getattr(record, 'decision_id', None))})")
            print(f"  Expected Prev: {expected_prev}")
            print(f"  Actual Prev:   {stored_prev}")
            return False
            
        # 2. Check canonical hash of the row itself
        recomputed = compute_canonical_hash(record_dict)
        if recomputed != stored_hash:
            print(f"[{table_class.__tablename__}] TAMPERING DETECTED at index {i} (ID: {getattr(record, 'id', getattr(record, 'decision_id', None))})")
            print(f"  Stored Hash:     {stored_hash}")
            print(f"  Recomputed Hash: {recomputed}")
            return False
            
        expected_prev = stored_hash
        
    print(f"[{table_class.__tablename__}] Chain verification passed! ({len(records)} records)")
    return True

def run_verification():
    with SessionLocal() as db:
        decisions = db.query(DecisionRecord).order_by(DecisionRecord.timestamp.asc()).all()
        # Audit trails are strictly tied to decisions 1:1, so we order by rowid or decision's timestamp.
        # SQLite rowid is safest for sequential insertion order if no timestamp is present.
        audit_trails = db.query(AuditTrailRecord).order_by(AuditTrailRecord.decision_id).all() # Simplification for POC
        
        d_ok = verify_table_chain(DecisionRecord, decisions)
        a_ok = verify_table_chain(AuditTrailRecord, audit_trails)
        
        if d_ok and a_ok:
            print("\nSUCCESS: Entire database ledger is cryptographically sound.")
        else:
            print("\nFAILURE: Evidentiary integrity compromised.")

if __name__ == "__main__":
    run_verification()
