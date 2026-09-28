import csv
import os
from datetime import datetime, timedelta
from typing import List, Tuple
from core.models import Claim, Policy

def load_real_claims(csv_path: str = "data/insurance_claims.csv", split: str = "all", seed: int = 42) -> List[Tuple[Claim, Policy, bool, dict]]:
    """
    Loads real-shaped claims from the Kaggle dataset.
    split: "all", "train" (80%), or "test" (20%)
    Returns a list of tuples containing:
    - Claim model instance
    - Policy model instance
    - Ground truth boolean (True if fraud_reported == 'Y')
    - Raw dictionary of the row (for additional features used in rules/eval)
    
    DOCUMENTATION ON EXTRACTION STAGE:
    Given this dataset is already structured/tabular (not raw documents), the 
    intake.py / extraction.py LLM stage's role changes: it's no longer parsing 
    free text into fields, since the fields already exist. This phase tests the 
    RULES, FRAUD-SCORING, DECISION, and CALIBRATION stages against real data 
    distribution, not the extraction stage (extraction remains validated only 
    against earlier synthetic/document-based tests).
    """
    claims = []
    
    # Gap explicit documentation:
    # This dataset represents auto insurance, not travel insurance.
    # It does not contain an explicit 'date_filed' independent of 'incident_date'.
    # It does not contain an 'evidence_list' representing submitted documents.
    # It does not contain an 'expiry_date' for policy, fabricating +1 year.
    # It does not contain 'exclusions' for policy, leaving empty.
    # It does not contain 'holder_id' for policy, using policy_number as proxy.
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            # parse dates
            try:
                incident_date = datetime.strptime(row['incident_date'], '%Y-%m-%d')
            except ValueError:
                incident_date = datetime.now()
            
            try:
                policy_bind_date = datetime.strptime(row['policy_bind_date'], '%Y-%m-%d')
            except ValueError:
                policy_bind_date = datetime.now()
                
            claim = Claim(
                id=f"REAL-CLM-{idx+1000}",
                policy_id=f"REAL-POL-{row['policy_number']}",
                date_filed=incident_date,  # GAP: Dataset lacks explicit filing date
                incident_date=incident_date,
                claim_type=row['incident_type'],
                amount=float(row['total_claim_amount']),
                cause=f"{row['collision_type']} ({row['incident_severity']})",
                evidence_list=[]  # GAP: Dataset is tabular, lacks document references
            )
            
            csl = row['policy_csl']
            csl_val = float(csl.split('/')[1]) * 1000 if '/' in csl else 0.0
            
            policy_number_real = f"REAL-POL-{row['policy_number']}"
            
            policy = Policy(
                policy_number=policy_number_real,
                product_type="auto", # Not in dataset explicitly, domain is auto insurance
                coverage_limits={
                    "csl": csl_val,
                    "deductable": float(row['policy_deductable']),
                    "umbrella": float(row['umbrella_limit'])
                },
                exclusions=[], # GAP: Dataset lacks explicit policy exclusions
                premium=float(row['policy_annual_premium']),
                effective_date=policy_bind_date,
                expiry_date=policy_bind_date + timedelta(days=365) if policy_bind_date else datetime.now(), # GAP
                holder_id=f"holder_{row['policy_number']}" # GAP
            )
            
            is_fraud = (row['fraud_reported'].strip().upper() == 'Y')
            claims.append((claim, policy, is_fraud, row))
            
    if split == "all":
        return claims
        
    import random
    random.seed(seed)
    
    # Shuffle predictably
    shuffled_claims = list(claims)
    random.shuffle(shuffled_claims)
    
    split_idx = int(0.8 * len(shuffled_claims))
    if split == "train":
        return shuffled_claims[:split_idx]
    elif split == "test":
        return shuffled_claims[split_idx:]
    else:
        raise ValueError("split must be 'all', 'train', or 'test'")

if __name__ == "__main__":
    loaded = load_real_claims()
    print(f"Loaded {len(loaded)} real claims.")
    print(f"Sample claim: {loaded[0][0]}")
    print(f"Sample label: {'Fraud' if loaded[0][1] else 'Legit'}")
