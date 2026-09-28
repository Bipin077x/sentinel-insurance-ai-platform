import json
from core.database import SessionLocal, AuditTrailRecord, DecisionRecord
from core.canonical import compute_canonical_hash

from core.models import Decision, AuditTrailEntry

def verify_chain(db_session=None) -> bool:
    """
    Walks every row in audit_trails and decisions in insertion order.
    Recomputes the canonical hash of each row to verify record_hash matches the content.
    Confirms prev_record_hash matches the actual hash of the prior row.
    """
    own_session = False
    if db_session is None:
        db_session = SessionLocal()
        own_session = True
        
    try:
        # Verify Decisions
        decisions = db_session.query(DecisionRecord).order_by(DecisionRecord.timestamp.asc()).all()
        prev_hash = None
        for row in decisions:
            if row.prev_record_hash != prev_hash:
                print(f"CHAIN BREAK: Decision {row.id} prev_record_hash ({row.prev_record_hash}) does not match actual prior hash ({prev_hash})")
                return False
                
            from datetime import timezone
            ts = row.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
                
            # Reconstruct Pydantic model exactly as done during insertion
            decision_dict = {
                "id": row.id,
                "function_type": row.function_type,
                "subject_id": row.subject_id,
                "outcome": row.outcome,
                "confidence_score": row.confidence_score,
                "confidence_source": row.confidence_source,
                "rules_fired": json.loads(row.rules_fired),
                "reasoning_text": row.reasoning_text,
                "model_version": row.model_version,
                "timestamp": ts,
                "status": row.status,
                "compliance_ruleset_hash": row.compliance_ruleset_hash,
                "prompt_hash": row.prompt_hash,
                "record_hash": row.record_hash,
                "prev_record_hash": row.prev_record_hash
            }
            decision_model = Decision(**decision_dict)
            hash_dict = decision_model.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
            hash_dict['prev_record_hash'] = row.prev_record_hash
            
            actual_hash = compute_canonical_hash(hash_dict)
            if actual_hash != row.record_hash:
                print(f"TAMPERING DETECTED: Decision {row.id} record_hash ({row.record_hash}) does not match recomputed hash ({actual_hash})")
                return False
            prev_hash = actual_hash
            
        # Verify Audit Trails (using decision timestamp order)
        audit_trails = db_session.query(AuditTrailRecord).join(DecisionRecord).order_by(DecisionRecord.timestamp.asc()).all()
        prev_hash = None
        for row in audit_trails:
            if row.prev_record_hash != prev_hash:
                print(f"CHAIN BREAK: AuditTrail {row.decision_id} prev_record_hash ({row.prev_record_hash}) does not match actual prior hash ({prev_hash})")
                return False
                
            # Reconstruct Pydantic model for AuditTrail
            audit_dict = {
                "decision_id": row.decision_id,
                "inputs_hash": row.inputs_hash,
                "inputs_snapshot": json.loads(row.inputs_snapshot),
                "rule_results": json.loads(row.rule_results),
                "model_prompt_version": row.model_prompt_version,
                "compliance_ruleset_hash": row.compliance_ruleset_hash,
                "prompt_hash": row.prompt_hash,
                "reviewer_id": row.reviewer_id,
                "override_reason": row.override_reason,
                "record_hash": row.record_hash,
                "prev_record_hash": row.prev_record_hash
            }
            audit_model = AuditTrailEntry(**audit_dict)
            hash_dict = audit_model.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
            hash_dict['prev_record_hash'] = row.prev_record_hash
            
            actual_hash = compute_canonical_hash(hash_dict)
            if actual_hash != row.record_hash:
                print(f"TAMPERING DETECTED: AuditTrail {row.decision_id} record_hash ({row.record_hash}) does not match recomputed hash ({actual_hash})")
                return False
            prev_hash = actual_hash
            
        print("Chain verification passed. No tampering detected.")
        return True
    finally:
        if own_session:
            db_session.close()

def verify_single_decision(decision_id: str, db_session=None) -> bool:
    """
    Verifies that a specific decision and its audit trail are untampered 
    by checking its canonical hash against its record_hash.
    """
    own_session = False
    if db_session is None:
        db_session = SessionLocal()
        own_session = True
        
    try:
        row = db_session.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not row:
            raise ValueError(f"Decision {decision_id} not found")
            
        from datetime import timezone
        ts = row.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
            
        decision_dict = {
            "id": row.id,
            "function_type": row.function_type,
            "subject_id": row.subject_id,
            "outcome": row.outcome,
            "confidence_score": row.confidence_score,
            "confidence_source": row.confidence_source,
            "rules_fired": json.loads(row.rules_fired),
            "reasoning_text": row.reasoning_text,
            "model_version": row.model_version,
            "timestamp": ts,
            "status": row.status,
            "compliance_ruleset_hash": row.compliance_ruleset_hash,
            "prompt_hash": row.prompt_hash,
            "record_hash": row.record_hash,
            "prev_record_hash": row.prev_record_hash
        }
        decision_model = Decision(**decision_dict)
        hash_dict = decision_model.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
        hash_dict['prev_record_hash'] = row.prev_record_hash
        
        actual_hash = compute_canonical_hash(hash_dict)
        if actual_hash != row.record_hash:
            raise ValueError(f"TAMPERING DETECTED: Decision {row.id} record_hash does not match recomputed hash.")

        audit_row = db_session.query(AuditTrailRecord).filter(AuditTrailRecord.decision_id == decision_id).first()
        if audit_row:
            audit_dict = {
                "decision_id": audit_row.decision_id,
                "inputs_hash": audit_row.inputs_hash,
                "inputs_snapshot": json.loads(audit_row.inputs_snapshot),
                "rule_results": json.loads(audit_row.rule_results),
                "model_prompt_version": audit_row.model_prompt_version,
                "compliance_ruleset_hash": audit_row.compliance_ruleset_hash,
                "prompt_hash": audit_row.prompt_hash,
                "reviewer_id": audit_row.reviewer_id,
                "override_reason": audit_row.override_reason,
                "record_hash": audit_row.record_hash,
                "prev_record_hash": audit_row.prev_record_hash
            }
            audit_model = AuditTrailEntry(**audit_dict)
            audit_hash_dict = audit_model.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
            audit_hash_dict['prev_record_hash'] = audit_row.prev_record_hash
            
            actual_audit_hash = compute_canonical_hash(audit_hash_dict)
            if actual_audit_hash != audit_row.record_hash:
                raise ValueError(f"TAMPERING DETECTED: AuditTrail {audit_row.decision_id} record_hash does not match recomputed hash.")

        return True
    finally:
        if own_session:
            db_session.close()

if __name__ == "__main__":
    verify_chain()
