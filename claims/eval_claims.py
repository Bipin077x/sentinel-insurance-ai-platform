import json
from core.database import SessionLocal, DecisionRecord
from core.chain_verify import verify_chain

def evaluate_claims():
    with open("ground_truth.json", "r") as f:
        ground_truth = json.load(f)
        
    gt_map = {item['claim_id']: item['expected_outcome'] for item in ground_truth}
    
    with SessionLocal() as db:
        decisions = db.query(DecisionRecord).filter(DecisionRecord.function_type == "claims").all()
        
    auto_decided = 0
    routed_to_review = 0
    correct = 0
    incorrect = 0
    review_reasons = []
    incorrect_cases = []
    
    for d in decisions:
        gt = gt_map.get(d.subject_id)
        if not gt:
            continue
            
        if d.status == "auto_decided":
            auto_decided += 1
            if d.outcome == gt:
                correct += 1
            else:
                incorrect += 1
                incorrect_cases.append({
                    "id": d.subject_id,
                    "gt": gt,
                    "decided": d.outcome,
                    "reasoning": d.reasoning_text,
                    "confidence": d.confidence_score,
                    "decision_id": d.id
                })
        elif d.status == "pending_review":
            routed_to_review += 1
            review_reasons.append(f"{d.subject_id}: {d.reasoning_text.splitlines()[-1] if d.reasoning_text else 'Unknown'}")
            if gt == "review":
                correct += 1
            else:
                pass
                
    total = len(decisions)
    print("--- Claims Evaluation ---")
    print(f"Total claims evaluated: {total}")
    print(f"Auto-decided: {auto_decided} ({auto_decided/total*100:.1f}%)")
    print(f"Routed to human review: {routed_to_review} ({routed_to_review/total*100:.1f}%)")
    
    if incorrect_cases:
        print("\n--- Incorrect Auto-Decided Cases Breakdown ---")
        for ic in incorrect_cases:
            print(f"ID: {ic['id']} | GT: {ic['gt']} | Decided: {ic['decided']}")
            print(f"  Reasoning: {ic['reasoning']}")
            
            # To get fraud_score, we'd need to parse inputs_snapshot from AuditTrail
            from core.database import AuditTrailRecord
            at = db.query(AuditTrailRecord).filter(AuditTrailRecord.decision_id == ic['decision_id']).first()
            if at:
                snap = json.loads(at.inputs_snapshot)
                print(f"  Fraud Score: {snap.get('fraud_score')}")
                print(f"  Fraud Flags: {snap.get('fraud_flags')}")
                print(f"  Calibrated Confidence: {ic['confidence']}")
    
    if routed_to_review > 0:
        print("\nClaims routed to review (with mechanism):")
        for reason in review_reasons:
            print(f"  {reason}")
    
    if auto_decided > 0:
        print(f"Accuracy on auto-decided cases: {correct/auto_decided*100:.1f}%")
        
    # Check bad claims
    with SessionLocal() as db:
        bad_decisions = db.query(DecisionRecord).filter(
            DecisionRecord.function_type == "extraction_validation"
        ).all()
        
    print(f"\nCaught {len(bad_decisions)} invalid claims at extraction stage.")
    for bd in bad_decisions:
        print(f"  {bd.subject_id}: {bd.reasoning_text}")
        
    print("\n--- Integrity Verification ---")
    is_valid = verify_chain()
    if is_valid:
        print("Audit trail and decision chain verification PASSED.")
    else:
        print("Audit trail verification FAILED.")

if __name__ == "__main__":
    evaluate_claims()
