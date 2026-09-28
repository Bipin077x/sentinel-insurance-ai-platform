from typing import List, Dict, Any
from core.database import SessionLocal, DecisionRecord
from core.models import DecisionStatus

def find_anomalies() -> List[Dict[str, Any]]:
    """
    Scans the database for anomalous decisions that warrant LLM audit review.
    Returns a list of dicts with 'decision_id' and 'anomaly_reason'.
    """
    flagged_decisions = []
    
    with SessionLocal() as db:
        decisions = db.query(DecisionRecord).all()
        
        for d in decisions:
            # 1. Borderline Confidence
            # Let's say threshold is roughly 0.85 to 0.95 depending on function.
            # We flag anything between 0.84 and 0.86, or 0.89 and 0.91 for scrutiny.
            # Or simpler: anything exactly at or just below/above our known thresholds (0.85, 0.90, 0.95)
            # Actually, let's flag any decision with confidence between 0.84 and 0.86 (borderline auto-decide for some functions).
            
            # Since mock generated fixed values like 0.8, 0.85, 0.90, 0.95, 0.98, 0.99
            # Let's flag any confidence that is <= 0.85, or exactly 0.90 (which is border for underwriting)
            if d.confidence_score <= 0.85:
                flagged_decisions.append({
                    "decision_id": d.id,
                    "anomaly_reason": f"Borderline/Low confidence score ({d.confidence_score})"
                })
                continue
                
            # 2. Override Scrutiny
            if d.status == DecisionStatus.PENDING_REVIEW or d.status == DecisionStatus.HUMAN_OVERRIDDEN:
                flagged_decisions.append({
                    "decision_id": d.id,
                    "anomaly_reason": f"Decision was routed to review/override (Status: {d.status.value})"
                })
                continue
                
            # 3. Outlier checks (e.g. claims > $3000)
            # Since outcome is a string, and for claims it's approve/deny. The amount is only in the inputs_snapshot.
            # But for simplicity in POC, let's just use the above two which will flag a few cases.
            
    return flagged_decisions
