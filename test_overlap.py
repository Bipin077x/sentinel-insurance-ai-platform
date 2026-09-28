import sys
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data.load_real_claims import load_real_claims
from claims.fraud_flags import evaluate_fraud_flags
from audit.anomaly_detection import find_anomalies

def test_overlap():
    claims_data = load_real_claims("data/insurance_claims.csv", split="all")
    
    # We already have anomaly detection flags stored in DB? No, eval_real_claims_anomaly.py ran it.
    # To be safe, we will just run eval_real_claims_anomaly's pipeline here or we can just fetch from DB.
    # Actually, we can just run the anomaly script first, then this one.
    
    # Let's run it all in one
    import eval_real_claims_anomaly
    eval_real_claims_anomaly.main()
    
    flags = find_anomalies()
    
    anomaly_flagged_ids = set()
    for flag in flags:
        for did in flag.decision_ids:
            anomaly_flagged_ids.add(did.replace("dec_", ""))
            
    print(f"\nAnomaly Flagged claim IDs: {anomaly_flagged_ids}")
    
    overlap = 0
    rule_flagged = 0
    
    for claim, policy, is_fraud, raw in claims_data:
        score, f_flags = evaluate_fraud_flags(claim)
        
        if score >= 0.5:
            rule_flagged += 1
            if claim.id in anomaly_flagged_ids:
                overlap += 1
                
    print(f"\nRule-based Fraud Flags (score >= 0.5): {rule_flagged} cases")
    print(f"Anomaly Detection Flags (amount outliers): {len(anomaly_flagged_ids)} cases")
    print(f"Overlap: {overlap} cases")

if __name__ == "__main__":
    # Suppress normal output
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        test_overlap()
    finally:
        out = sys.stdout.getvalue()
        sys.stdout = old_stdout
        print("--- Overlap Report ---")
        lines = out.split("\n")
        # Just print the relevant part
        for line in lines[-5:]:
            print(line)
