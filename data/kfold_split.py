import sys
import os
import random
from typing import List, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.load_real_claims import load_real_claims
from core.models import Claim, Policy

def get_stratified_folds(csv_path: str = "data/insurance_claims.csv", k: int = 5, seed: int = 42) -> List[List[Tuple[Claim, Policy, bool, dict]]]:
    """
    Loads all claims and splits them into k stratified folds.
    Returns a list of k folds.
    """
    claims_data = load_real_claims(csv_path, split="all")
    
    # Separate into positive (fraud) and negative (legit) classes
    fraud_cases = [c for c in claims_data if c[2]]
    legit_cases = [c for c in claims_data if not c[2]]
    
    random.seed(seed)
    random.shuffle(fraud_cases)
    random.shuffle(legit_cases)
    
    folds = [[] for _ in range(k)]
    
    # Distribute fraud cases
    for i, case in enumerate(fraud_cases):
        folds[i % k].append(case)
        
    # Distribute legit cases
    for i, case in enumerate(legit_cases):
        folds[i % k].append(case)
        
    # Shuffle within each fold
    for fold in folds:
        random.shuffle(fold)
        
    return folds

if __name__ == "__main__":
    folds = get_stratified_folds()
    print(f"Total folds: {len(folds)}")
    for i, fold in enumerate(folds):
        total = len(fold)
        frauds = sum(1 for c in fold if c[2])
        print(f"Fold {i+1}: {total} cases | {frauds} frauds | {frauds/total:.1%} fraud rate")
