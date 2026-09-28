import json
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base, DecisionRecord, AuditTrailRecord
from data.load_real_claims import load_real_claims
from core.models import FunctionType, DecisionStatus
from audit.anomaly_detection import detect_amount_outliers, detect_near_duplicates

# Create a temporary in-memory database for evaluation
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=engine)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_anomaly_eval():
    claims = load_real_claims()
    print(f"Loaded {len(claims)} claims for anomaly evaluation.")
    
    fraud_map = {claim.id: is_fraud for claim, is_fraud, _ in claims}
    
    with TestSessionLocal() as db:
        
        for claim, is_fraud, raw in claims:
            # We insert mock decisions to let anomaly_detection process them
            # We set outcome="approve" for all so they get grouped together for Z-score
            dec_id = f"dec_{claim.id}"
            
            d_rec = DecisionRecord(
                id=dec_id,
                function_type=FunctionType.CLAIMS,
                subject_id=claim.id,
                outcome="approve",
                confidence_score=0.99,
                rules_fired=json.dumps([]),
                reasoning_text="Mock for anomaly eval",
                model_version="mock",
                status=DecisionStatus.AUTO_DECIDED,
                record_hash=f"hash_{claim.id}",
                timestamp=claim.incident_date # Using incident_date to avoid timing anomalies all clustering today
            )
            
            a_rec = AuditTrailRecord(
                decision_id=dec_id,
                inputs_hash=f"ihash_{claim.id}",
                inputs_snapshot=json.dumps({
                    "claim": {
                        "amount": claim.amount,
                        "policy_id": claim.policy_id,
                        "claim_type": claim.claim_type
                    }
                }),
                rule_results=json.dumps([]),
                model_prompt_version="v1",
                record_hash=f"ahash_{claim.id}"
            )
            
            db.add(d_rec)
            db.add(a_rec)
            
        db.commit()

    with TestSessionLocal() as db:
        records = (
            db.query(DecisionRecord, AuditTrailRecord)
            .join(AuditTrailRecord, DecisionRecord.id == AuditTrailRecord.decision_id)
            .all()
        )
        flags = []
        flags.extend(detect_amount_outliers(records))
        flags.extend(detect_near_duplicates(records))
    
    print(f"\n--- Anomaly Detection Results ---")
    amount_flags = [f for f in flags if f.detector == "amount_outlier"]
    near_dup_flags = [f for f in flags if f.detector == "near_duplicate"]
    
    print(f"Amount Outliers Flagged: {sum(len(f.decision_ids) for f in amount_flags)}")
    print(f"Near Duplicates Flagged: {sum(len(f.decision_ids) for f in near_dup_flags)}")
    
    # Eval Amount Outliers against ground truth
    flagged_claim_ids = set()
    for f in amount_flags:
        for did in f.decision_ids:
            cid = did.replace("dec_", "")
            flagged_claim_ids.add(cid)
            
    true_positives = sum(1 for cid in flagged_claim_ids if fraud_map[cid])
    total_flagged = len(flagged_claim_ids)
    
    if total_flagged > 0:
        precision = true_positives / total_flagged
        print(f"\nAmount Outlier Precision: {precision*100:.1f}% ({true_positives}/{total_flagged} were true frauds)")
    else:
        print("\nAmount Outlier Precision: N/A (0 flagged)")

if __name__ == "__main__":
    run_anomaly_eval()
