import sys
from dotenv import load_dotenv
load_dotenv()
import os
import yaml

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data.load_real_claims import load_real_claims
from claims.rules import check_rules
from claims.fraud_flags import evaluate_fraud_flags
from claims.decision import make_decision
from core.database import Base, engine, SessionLocal, PolicyRecord
from core.calibration import compute_semantic_entropy
from core.model_registry import check_and_log_model_version
from core.llm_client import get_cost, TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS
import json

def test_stage2():
    config_path = "config/model_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "gpt-4o-2024-08-06"}, f)
        
    check_and_log_model_version()
    
    print("Running Stage 2 Small-Sample Sanity Check (20 records)...")
    Base.metadata.create_all(bind=engine)
    claims_data = load_real_claims("data/insurance_claims.csv", split="all")[:20]
    
    with SessionLocal() as db:
        for claim, policy, is_fraud, raw in claims_data:
            if not db.query(PolicyRecord).filter_by(policy_number=policy.policy_number).first():
                pr = PolicyRecord(
                    policy_number=policy.policy_number,
                    product_type=policy.product_type,
                    coverage_limits=json.dumps(policy.coverage_limits),
                    exclusions=json.dumps(policy.exclusions),
                    premium=policy.premium,
                    effective_date=policy.effective_date,
                    expiry_date=policy.expiry_date,
                    holder_id=policy.holder_id
                )
                db.add(pr)
        db.commit()

    ambiguous_confidences = []
    clear_confidences = []
    
    for claim, policy, is_fraud, raw in claims_data:
        rule_results = check_rules(claim)
        fraud_score, fraud_flags = evaluate_fraud_flags(claim)
        
        def _claims_llm_caller():
            return make_decision(claim, rule_results, fraud_score, fraud_flags)
            
        try:
            decision_out, _, calibrated_confidence, _ = compute_semantic_entropy(_claims_llm_caller, num_samples=5)
            
            # Grouping by pre-existing dataset labels independently of pipeline output
            if not is_fraud:
                clear_confidences.append(calibrated_confidence)
            else:
                ambiguous_confidences.append(calibrated_confidence)
                
            print(f"Case {claim.id}: Outcome {decision_out.outcome}, Confidence {calibrated_confidence:.2f}")
        except Exception as e:
            print(f"Case {claim.id} failed: {e}")
            break

    print(f"\nClear Cases Average Confidence: {sum(clear_confidences)/len(clear_confidences) if clear_confidences else 0:.2f} (n={len(clear_confidences)})")
    print(f"Ambiguous Cases Average Confidence: {sum(ambiguous_confidences)/len(ambiguous_confidences) if ambiguous_confidences else 0:.2f} (n={len(ambiguous_confidences)})")
    
    print(f"\nTotal Tokens used in Stage 2: {TOTAL_INPUT_TOKENS} input, {TOTAL_OUTPUT_TOKENS} output")
    cost = get_cost()
    print(f"Total Stage 2 cost: ${cost:.4f}")
    
    # 20 records took `cost`. 1000 records * 5 folds is 5000 cases (well, 5 * 200 = 1000 test cases total across folds, 
    # but training also takes some processing if it uses LLM. Actually, training in Phase 13 was rule-based, so only 1000 eval cases).
    # Oh wait, Phase 13 eval evaluates 200 * 5 = 1000 test cases total across folds.
    # 1000 cases / 20 cases = 50x multiplier.
    est_full_cost = cost * 50
    print(f"\nExtrapolated cost for full 1000-case k-fold evaluation: ~${est_full_cost:.2f}")

    # Revert config
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "mock-llm-1.0-0613"}, f)

if __name__ == "__main__":
    test_stage2()
