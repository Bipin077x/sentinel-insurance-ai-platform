import sys
import os

# Add to path to allow importing core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data.load_real_claims import load_real_claims
from claims.rules import check_rules
from claims.fraud_flags import evaluate_fraud_flags
from core.database import Base, engine, SessionLocal, PolicyRecord, ClaimRecord
import json

def setup_db():
    Base.metadata.create_all(bind=engine)

def main():
    setup_db()
    
    claims_data = load_real_claims("data/insurance_claims.csv")
    print(f"Loaded {len(claims_data)} claims")
    
    # Store policies in DB so check_rules works
    with SessionLocal() as db:
        for c, p, is_fraud, raw in claims_data:
            # Check if policy exists
            if not db.query(PolicyRecord).filter_by(policy_number=p.policy_number).first():
                pr = PolicyRecord(
                    policy_number=p.policy_number,
                    product_type=p.product_type,
                    coverage_limits=json.dumps(p.coverage_limits),
                    exclusions=json.dumps(p.exclusions),
                    premium=p.premium,
                    effective_date=p.effective_date,
                    expiry_date=p.expiry_date,
                    holder_id=p.holder_id
                )
                db.add(pr)
        db.commit()

    breakages = {}
    rule_stats = {}
    fraud_score_stats = []
    
    # test check_rules
    for idx, (claim, policy, is_fraud, raw) in enumerate(claims_data):
        try:
            results = check_rules(claim)
            for r in results:
                if r.rule_name not in rule_stats:
                    rule_stats[r.rule_name] = {"passed": 0, "failed": 0}
                if r.passed:
                    rule_stats[r.rule_name]["passed"] += 1
                else:
                    rule_stats[r.rule_name]["failed"] += 1
                    
            f_score, f_flags = evaluate_fraud_flags(claim)
            fraud_score_stats.append((f_score, is_fraud, f_flags))
        except Exception as e:
            err_type = type(e).__name__
            msg = str(e)
            breakages[f"{err_type}: {msg}"] = breakages.get(f"{err_type}: {msg}", 0) + 1
            
    print("Rule Check Breakages (Runtime Errors):", breakages)
    print("Rule Pass/Fail Stats:", json.dumps(rule_stats, indent=2))
    
    fraud_gt = [x for x in fraud_score_stats if x[1]]
    legit_gt = [x for x in fraud_score_stats if not x[1]]
    
    avg_score_fraud = sum(x[0] for x in fraud_gt) / len(fraud_gt) if fraud_gt else 0
    avg_score_legit = sum(x[0] for x in legit_gt) / len(legit_gt) if legit_gt else 0
    
    print(f"Average Fraud Score for Ground Truth Fraud ({len(fraud_gt)} cases): {avg_score_fraud}")
    print(f"Average Fraud Score for Ground Truth Legit ({len(legit_gt)} cases): {avg_score_legit}")
    
if __name__ == "__main__":
    main()
