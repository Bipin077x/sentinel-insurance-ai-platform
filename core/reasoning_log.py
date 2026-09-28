import json
from typing import List, Optional, Any, Dict
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.database import SessionLocal, DecisionRecord, AuditTrailRecord, RawDocumentRecord
import uuid
from datetime import datetime, timezone, timedelta

def log_decision(decision: Decision, audit_trail: AuditTrailEntry, raw_unredacted_text: Optional[str] = None):
    """
    Persists a decision and its audit trail to SQLite securely using an append-only hash chain.
    If raw_unredacted_text is provided, it is securely persisted in a separate, short-lived storage.
    """
    from core.canonical import compute_canonical_hash
    from core.database import SessionLocal, DecisionRecord, AuditTrailRecord, RawDocumentRecord
    
    with SessionLocal() as db:
        # Get the previous row to construct the hash chain
        prev_decision = db.query(DecisionRecord).order_by(DecisionRecord.timestamp.desc()).first()
        prev_decision_hash = prev_decision.record_hash if prev_decision else None
        
        # Prepare Decision dictionary for hashing
        decision_dict = decision.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
        decision_dict['prev_record_hash'] = prev_decision_hash
        decision_hash = compute_canonical_hash(decision_dict)
        
        db_decision = DecisionRecord(
            id=decision.id,
            function_type=decision.function_type,
            subject_id=decision.subject_id,
            outcome=decision.outcome,
            confidence_score=decision.confidence_score,
            confidence_source=decision.confidence_source,
            rules_fired=json.dumps(decision.rules_fired),
            reasoning_text=decision.reasoning_text,
            model_version=decision.model_version,
            timestamp=decision.timestamp,
            status=decision.status,
            compliance_ruleset_hash=decision.compliance_ruleset_hash,
            prompt_hash=decision.prompt_hash,
            record_hash=decision_hash,
            prev_record_hash=prev_decision_hash
        )
        
        # Hash chain for Audit Trail
        prev_audit = db.query(AuditTrailRecord).order_by(AuditTrailRecord.decision_id.desc()).first() # Simplified ordering
        prev_audit_hash = prev_audit.record_hash if prev_audit else None
        
        audit_dict = audit_trail.model_dump(mode='json', exclude={'record_hash', 'prev_record_hash'})
        audit_dict['prev_record_hash'] = prev_audit_hash
        audit_hash = compute_canonical_hash(audit_dict)
        
        # Create audit trail record
        db_audit = AuditTrailRecord(
            decision_id=audit_trail.decision_id,
            inputs_hash=audit_trail.inputs_hash,
            inputs_snapshot=json.dumps(audit_trail.inputs_snapshot),
            rule_results=json.dumps(audit_trail.rule_results),
            model_prompt_version=audit_trail.model_prompt_version,
            compliance_ruleset_hash=audit_trail.compliance_ruleset_hash,
            prompt_hash=audit_trail.prompt_hash,
            reviewer_id=audit_trail.reviewer_id,
            override_reason=audit_trail.override_reason,
            record_hash=audit_hash,
            prev_record_hash=prev_audit_hash
        )
        
        db.add(db_decision)
        db.add(db_audit)
        
        # Save raw data if provided
        if raw_unredacted_text:
            from core.retention_policy import load_retention_policy
            policy, _ = load_retention_policy()
            retention_days = policy.get("raw_documents_pii_days", 30)
            
            db_raw = RawDocumentRecord(
                id=str(uuid.uuid4()),
                decision_id=decision.id,
                raw_content=raw_unredacted_text,
                retention_expiry=datetime.utcnow() + timedelta(days=retention_days)
            )
            db.add(db_raw)
            
        db.commit()

def get_decision_trail(decision_id: str) -> Optional[Dict[str, Any]]:
    """Returns full reconstructed reasoning for that decision."""
    with SessionLocal() as db:
        record = db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first()
        if not record:
            return None
        
        # Reconstruct Pydantic models (or just return dicts)
        decision_dict = {
            "id": record.id,
            "function_type": record.function_type,
            "subject_id": record.subject_id,
            "outcome": record.outcome,
            "confidence_score": record.confidence_score,
            "confidence_source": record.confidence_source,
            "rules_fired": json.loads(record.rules_fired),
            "reasoning_text": record.reasoning_text,
            "model_version": record.model_version,
            "timestamp": record.timestamp,
            "status": record.status,
            "compliance_ruleset_hash": record.compliance_ruleset_hash,
            "prompt_hash": record.prompt_hash,
            "record_hash": record.record_hash,
            "prev_record_hash": record.prev_record_hash
        }
        
        audit_dict = None
        if record.audit_trail:
            audit_dict = {
                "decision_id": record.audit_trail.decision_id,
                "inputs_hash": record.audit_trail.inputs_hash,
                "inputs_snapshot": json.loads(record.audit_trail.inputs_snapshot),
                "rule_results": json.loads(record.audit_trail.rule_results),
                "model_prompt_version": record.audit_trail.model_prompt_version,
                "compliance_ruleset_hash": record.audit_trail.compliance_ruleset_hash,
                "prompt_hash": record.audit_trail.prompt_hash,
                "reviewer_id": record.audit_trail.reviewer_id,
                "override_reason": record.audit_trail.override_reason,
                "record_hash": record.audit_trail.record_hash,
                "prev_record_hash": record.audit_trail.prev_record_hash
            }
            
        return {
            "decision": Decision(**decision_dict),
            "audit_trail": AuditTrailEntry(**audit_dict) if audit_dict else None
        }

def query_decisions(filters: Dict[str, Any]) -> List[Decision]:
    """Pulls populations of past decisions based on filters."""
    with SessionLocal() as db:
        query = db.query(DecisionRecord)
        
        if "function_type" in filters:
            query = query.filter(DecisionRecord.function_type == filters["function_type"])
        if "status" in filters:
            query = query.filter(DecisionRecord.status == filters["status"])
        if "subject_id" in filters:
            query = query.filter(DecisionRecord.subject_id == filters["subject_id"])
            
        records = query.all()
        results = []
        for record in records:
            decision_dict = {
                "id": record.id,
                "function_type": record.function_type,
                "subject_id": record.subject_id,
                "outcome": record.outcome,
                "confidence_score": record.confidence_score,
                "confidence_source": record.confidence_source,
                "rules_fired": json.loads(record.rules_fired),
                "reasoning_text": record.reasoning_text,
                "model_version": record.model_version,
                "timestamp": record.timestamp,
                "status": record.status,
                "compliance_ruleset_hash": record.compliance_ruleset_hash,
                "prompt_hash": record.prompt_hash,
                "record_hash": record.record_hash,
                "prev_record_hash": record.prev_record_hash
            }
            results.append(Decision(**decision_dict))
        return results
