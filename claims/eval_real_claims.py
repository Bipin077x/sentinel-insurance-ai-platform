import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from data.load_real_claims import load_real_claims
from claims.rules import check_rules
from claims.fraud_flags import evaluate_fraud_flags
from core.database import SessionLocal, PolicyRecord, ClaimRecord
from core.models import RuleResult

def eval_real_claims():
    claims = load_real_claims()
    print(f"Loaded {len(claims)} claims for evaluation.")
    
    # 1. Setup Mock DB Policies
    with SessionLocal() as db:
        db.query(PolicyRecord).delete()
        db.query(ClaimRecord).delete()
        
        for claim, is_fraud, raw in claims:
            # We adjust the field mapping for effective_date so it doesn't break 'policy_active' 
            # due to arbitrary 20-year expiry cutoff.
            # Change: Set expiry_date to incident_date + 1 year to ensure it stays active.
            try:
                eff_date = datetime.strptime(raw['policy_bind_date'], '%Y-%m-%d')
            except ValueError:
                eff_date = claim.incident_date - timedelta(days=365)
                
            csl = raw['policy_csl']
            limit_per_accident = 100000.0  # Increased default threshold 
            if '/' in csl:
                # We multiply by 1000 since CSL is usually in thousands (e.g. 250/500 = $250k/$500k)
                limit_per_accident = float(csl.split('/')[0]) * 1000
                
            umbrella = float(raw['umbrella_limit'])
            total_limit = limit_per_accident + umbrella
            
            policy = PolicyRecord(
                policy_number=claim.policy_id,
                product_type="Auto",
                coverage_limits=json.dumps({ claim.claim_type: total_limit }),
                exclusions=json.dumps([]),
                premium=float(raw['policy_annual_premium']),
                effective_date=eff_date,
                expiry_date=claim.incident_date + timedelta(days=365), # Adjusted to avoid arbitrary expiration
                holder_id=raw['insured_zip']
            )
            db.merge(policy)
            
            claim_rec = ClaimRecord(
                id=claim.id,
                policy_id=claim.policy_id,
                date_filed=claim.date_filed,
                claim_type=claim.claim_type,
                amount=claim.amount,
                cause=claim.cause,
                evidence_list=json.dumps([])
            )
            db.merge(claim_rec)
        db.commit()

    # 2. Evaluate Claims
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0
    
    # Track actions
    auto_decided = 0
    escalated = 0
    
    for claim, is_fraud_truth, raw in claims:
        # Check Rules
        rule_results = check_rules(claim)
        all_passed = all(r.passed for r in rule_results)
        
        # Check Fraud Flags
        fraud_score, fraud_flags = evaluate_fraud_flags(claim)
        
        # Pipeline logic mockup (since we don't want to call mock LLM 1000 times for semantic checks)
        # If rules fail -> deny (auto_decided)
        # If fraud_score > 0.85 -> escalate
        # If all passed and fraud_score <= 0.85 -> approve (auto_decided)
        
        is_escalated = (fraud_score > 0.85) or (not all_passed)
        is_fraud_pred = is_escalated # We treat escalated/denied as a "fraud/anomalous" prediction for eval purposes
        
        if not is_escalated:
            auto_decided += 1
        else:
            escalated += 1
            
        if is_fraud_truth and is_fraud_pred:
            true_positives += 1
        elif not is_fraud_truth and is_fraud_pred:
            false_positives += 1
        elif not is_fraud_truth and not is_fraud_pred:
            true_negatives += 1
        elif is_fraud_truth and not is_fraud_pred:
            false_negatives += 1

    total = len(claims)
    accuracy = (true_positives + true_negatives) / total
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_positives) if (true_positives + false_negatives) > 0 else 0
    base_rate = sum(1 for c in claims if c[1]) / total
    naive_accuracy = 1.0 - base_rate # "always predict not-fraud"

    print(f"\n--- Phase 12 Claims Evaluation ---")
    print(f"Total evaluated: {total}")
    print(f"Base Fraud Rate: {base_rate*100:.1f}%")
    print(f"Naive 'Predict Legit' Accuracy: {naive_accuracy*100:.1f}%")
    print(f"Pipeline Accuracy: {accuracy*100:.1f}%")
    print(f"Precision (Fraud): {precision*100:.1f}%")
    print(f"Recall (Fraud): {recall*100:.1f}%")
    
    print(f"\nBreakdown:")
    print(f"True Positives: {true_positives}")
    print(f"False Positives: {false_positives}")
    print(f"True Negatives: {true_negatives}")
    print(f"False Negatives: {false_negatives}")
    
    print(f"\nAction Split:")
    print(f"Auto-decided: {auto_decided} ({(auto_decided/total)*100:.1f}%)")
    print(f"Escalated (Manual Review): {escalated} ({(escalated/total)*100:.1f}%)")

if __name__ == "__main__":
    eval_real_claims()
