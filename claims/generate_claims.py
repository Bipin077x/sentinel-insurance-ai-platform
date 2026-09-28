import json
import random
from datetime import datetime, timedelta, timezone
from core.database import SessionLocal, init_db, PolicyRecord, ClaimRecord
from core.models import Policy

def generate_synthetic_data():
    init_db()
    
    policies = []
    claims_raw = []
    ground_truths = []
    
    now = datetime.now(timezone.utc)
    
    with SessionLocal() as db:
        # Clear existing to prevent duplicate IDs across runs
        db.query(ClaimRecord).delete()
        db.query(PolicyRecord).delete()
        
        for i in range(1, 31):
            policy_num = f"POL-{1000+i}"
            holder_id = f"HOLDER-{i}"
            claim_id = f"CLM-{1000+i}"
            
            # Scenario logic
            if i <= 10:
                scenario_type = "approve"
            elif i <= 20:
                scenario_type = "deny"
            else:
                scenario_type = "ambiguous"
                
            is_expired = (scenario_type == "deny" and i % 3 == 0)
            
            # Policy Generation
            effective = now - timedelta(days=365) if is_expired else now - timedelta(days=30)
            expiry = now - timedelta(days=1) if is_expired else now + timedelta(days=335)
            
            # For "claim immediately after purchase" fraud flag
            if scenario_type == "ambiguous" and i % 2 == 0:
                effective = now - timedelta(hours=12)
                expiry = effective + timedelta(days=365)
                
            policy = Policy(
                policy_number=policy_num,
                product_type="travel",
                coverage_limits={"trip_cancellation": 5000.0, "delay": 500.0},
                exclusions=["pre-existing condition", "extreme sports", "pandemic"],
                premium=150.0,
                effective_date=effective,
                expiry_date=expiry,
                holder_id=holder_id
            )
            policies.append(policy)
            
            db_policy = PolicyRecord(
                policy_number=policy.policy_number,
                product_type=policy.product_type,
                coverage_limits=json.dumps(policy.coverage_limits),
                exclusions=json.dumps(policy.exclusions),
                premium=policy.premium,
                effective_date=policy.effective_date,
                expiry_date=policy.expiry_date,
                holder_id=policy.holder_id
            )
            db.merge(db_policy)
            
            # Claim Generation
            date_filed = now - timedelta(hours=random.randint(1, 48))
            evidence = ["booking_receipt.pdf", "cancellation_email.pdf"]
            
            if scenario_type == "approve":
                amount = random.randint(500, 2500) + random.random() # non-round
                raw_text = f"My trip was cancelled because the airline went bankrupt. I spent ${amount:.2f} on tickets. Please reimburse me. Policy {policy_num}."
                gt = "approve"
            elif scenario_type == "deny":
                if is_expired:
                    amount = 1000.0
                    raw_text = f"I am filing a claim for trip cancellation. My flight was cancelled due to bad weather. I want to claim ${amount:.2f}. My policy is {policy_num}."
                elif i % 3 == 1:
                    amount = 2000.0
                    raw_text = f"I had to cancel my trip because I went skydiving and broke my leg. Claiming ${amount:.2f} under {policy_num}."
                else: # Exceeds limit
                    amount = 6000.0
                    raw_text = f"My expensive trip was cancelled due to illness. Total cost was ${amount:.2f}. Need reimbursement on policy {policy_num}."
                gt = "deny"
            else: # ambiguous
                amount = 5000.0 if i % 2 == 0 else (random.randint(100, 2000) * 100.0) # Round numbers
                evidence = [] if i % 3 == 0 else ["receipt.jpg"]
                raw_text = f"Claiming ${amount:.2f} for trip cancellation. I just bought this policy {policy_num} yesterday and my trip got cancelled today due to unspecified personal reasons. Can't provide documents right now."
                gt = "review"
                
            claims_raw.append({
                "claim_id": claim_id,
                "policy_id": policy_num,
                "date_filed": date_filed.isoformat(),
                "raw_text": raw_text,
                "evidence": evidence
            })
            
            ground_truths.append({
                "claim_id": claim_id,
                "expected_outcome": gt
            })
            
        # Add a duplicate claim record matching an existing record (for the duplicate check rule)
        # We simulate this by having a claim already in the DB.
        db_claim = ClaimRecord(
            id="CLM-9999", # Different ID
            policy_id="POL-1015", # Belongs to a "deny" scenario claim
            date_filed=now - timedelta(days=2),
            claim_type="trip_cancellation",
            amount=2000.0,
            cause="skydiving",
            evidence_list="[]"
        )
        db.merge(db_claim)
            
        db.commit()
        
    # Inject bad synthetic data to test deterministic fallback validation
    bad_claim_1 = {
        "claim_id": "CLM-BAD-1001",
        "policy_id": "POL-BAD-1001",
        "date_filed": (now + timedelta(days=5)).isoformat(), # Future date
        "raw_text": "Filing a claim for $-50.0 due to Fell down. Happened on my trip. My SSN is 123-45-6789.",
        "claim_type": "trip_cancellation",
        "amount": -50.0, # Negative amount
        "cause": "Fell down",
        "evidence": ["doc_1.pdf"]
    }
    bad_claim_2 = {
        "claim_id": "CLM-BAD-1002",
        "policy_id": "POL-BAD-1002",
        "date_filed": (now - timedelta(days=5)).isoformat(),
        "raw_text": "Filing a claim for $3000000.0 due to Missed flight. Happened on my trip.",
        "claim_type": "trip_cancellation",
        "amount": 3000000.0, # Too high
        "cause": "Missed flight",
        "evidence": ["doc_2.pdf"]
    }
    claims_raw.extend([bad_claim_1, bad_claim_2])
    
    # Generate bad policies so db logic doesn't crash on policy not found
    with SessionLocal() as db:
        for p_id in ["POL-BAD-1001", "POL-BAD-1002"]:
            policy = Policy(
                policy_number=p_id,
                product_type="travel",
                coverage_limits={"trip_cancellation": 5000.0, "delay": 500.0},
                exclusions=[],
                premium=150.0,
                effective_date=now - timedelta(days=30),
                expiry_date=now + timedelta(days=335),
                holder_id="BAD-HOLDER"
            )
            db.merge(PolicyRecord(
                policy_number=policy.policy_number,
                product_type=policy.product_type,
                coverage_limits=json.dumps(policy.coverage_limits),
                exclusions=json.dumps(policy.exclusions),
                premium=policy.premium,
                effective_date=policy.effective_date,
                expiry_date=policy.expiry_date,
                holder_id=policy.holder_id
            ))
        db.commit()
        
    with open("synthetic_claims.json", "w") as f:
        json.dump(claims_raw, f, indent=2)
        
    with open("ground_truth.json", "w") as f:
        json.dump(ground_truths, f, indent=2)
        
    print("Generated 30 synthetic claims and policies, plus 2 bad claims.")

if __name__ == "__main__":
    generate_synthetic_data()
