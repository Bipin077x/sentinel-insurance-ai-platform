import json
from datetime import datetime, timedelta
from data.load_real_claims import load_real_claims
from claims.rules import check_rules
from core.database import SessionLocal, PolicyRecord, ClaimRecord
from collections import Counter

def run_asis_test():
    claims = load_real_claims()
    print(f"Loaded {len(claims)} claims.")
    
    # Insert mock policies into DB so 'policy_exists' doesn't fail
    with SessionLocal() as db:
        # Clear existing to be safe
        db.query(PolicyRecord).delete()
        db.query(ClaimRecord).delete()
        
        for claim, is_fraud, raw in claims:
            # Parse bind date
            try:
                eff_date = datetime.strptime(raw['policy_bind_date'], '%Y-%m-%d')
            except ValueError:
                eff_date = datetime.now() - timedelta(days=365)
            
            # Extract coverage limit from CSL (e.g. 250/500)
            csl = raw['policy_csl']
            limit_per_accident = 1000.0  # default
            if '/' in csl:
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
                expiry_date=eff_date + timedelta(days=365*20), # arbitrary future date
                holder_id=raw['insured_zip'] # just a proxy
            )
            # Use merge to handle potential duplicate policies in dataset
            db.merge(policy)
        db.commit()

    # Now evaluate rules
    rule_failures = Counter()
    total = 0
    
    for claim, is_fraud, raw in claims:
        total += 1
        results = check_rules(claim)
        for r in results:
            if not r.passed:
                rule_failures[r.rule_name] += 1
                
    print("\n--- Rule Evaluation Results (As-Is) ---")
    print(f"Total claims evaluated: {total}")
    for rule, count in rule_failures.items():
        print(f"Rule '{rule}' failed {count} times.")

if __name__ == "__main__":
    run_asis_test()
