from typing import List, Optional
from datetime import datetime, timedelta
from core.database import SessionLocal, DecisionRecord, ReviewRecord
from core.models import DecisionStatus

def list_pending(pipeline: Optional[str] = None, mechanism: Optional[str] = None, max_age_hours: Optional[int] = None) -> List[DecisionRecord]:
    with SessionLocal() as db:
        query = db.query(DecisionRecord).filter(DecisionRecord.status == DecisionStatus.PENDING_REVIEW)
        
        if pipeline:
            query = query.filter(DecisionRecord.function_type == pipeline.upper())
            
        if mechanism:
            query = query.filter(DecisionRecord.confidence_source == mechanism)
            
        if max_age_hours:
            cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
            query = query.filter(DecisionRecord.timestamp >= cutoff)
            
        return query.all()

def get_review_status(decision_id: str) -> Optional[ReviewRecord]:
    with SessionLocal() as db:
        return db.query(ReviewRecord).filter(ReviewRecord.decision_id == decision_id).first()
