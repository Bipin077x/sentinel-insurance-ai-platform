import json
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.models import Application
from underwriting.risk_scoring import evaluate_risk

def run_evaluation(json_path: str = "data/real_axa_underwriting.json"):
    with open(json_path, "r") as f:
        raw_apps = json.load(f)
        
    apps = []
    targets = []
    
    for r in raw_apps:
        app = Application(**r)
        apps.append(app)
        targets.append(1 if r["metadata"]["claim_target"] else 0)
        
    apps = np.array(apps)
    targets = np.array(targets)
    
    print(f"Total Applications: {len(apps)}")
    print(f"Total Claims: {sum(targets)}")
    print(f"Base Claim Rate: {sum(targets)/len(apps):.2%}")
    print("-" * 50)
    
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    fold_results = []
    
    for fold, (train_idx, test_idx) in enumerate(skf.split(apps, targets)):
        # We only use the test set for this fold to evaluate the stratification, 
        # so each fold evaluates 20% of the data, identically sized and distributed.
        fold_apps = apps[test_idx]
        fold_targets = targets[test_idx]
        
        tier_counts = {"Low": 0, "Medium": 0, "High": 0}
        tier_claims = {"Low": 0, "Medium": 0, "High": 0}
        
        for app, target in zip(fold_apps, fold_targets):
            # Run the UNCHANGED risk scoring formula
            risk_tier, _, _ = evaluate_risk(app)
            
            tier_counts[risk_tier] += 1
            if target == 1:
                tier_claims[risk_tier] += 1
                
        # Calculate rates
        fold_res = {}
        for t in ["Low", "Medium", "High"]:
            count = tier_counts[t]
            claims = tier_claims[t]
            rate = claims / count if count > 0 else 0
            fold_res[f"{t}_count"] = count
            fold_res[f"{t}_rate"] = rate
            
        fold_results.append(fold_res)
        
        print(f"Fold {fold+1}:")
        for t in ["Low", "Medium", "High"]:
            print(f"  {t} Tier: {fold_res[f'{t}_count']:<5d} cases | {fold_res[f'{t}_rate']:.2%} claim rate")
            
    print("-" * 50)
    print("AVERAGE ACROSS FOLDS:")
    avg_low = np.mean([r["Low_rate"] for r in fold_results])
    avg_med = np.mean([r["Medium_rate"] for r in fold_results])
    avg_high = np.mean([r["High_rate"] for r in fold_results])
    
    print(f"  Low Tier Average Claim Rate:    {avg_low:.2%}")
    print(f"  Medium Tier Average Claim Rate: {avg_med:.2%}")
    print(f"  High Tier Average Claim Rate:   {avg_high:.2%}")
    
    # Univariate checks
    print("-" * 50)
    print("UNIVARIATE SANITY CHECKS (All Data):")
    df = pd.DataFrame({
        "Duration": [a.trip_duration_days for a in apps],
        "Destination": [a.destination for a in apps],
        "Claim": targets
    })
    
    # Destination
    dest_rates = df.groupby("Destination")["Claim"].agg(["count", "mean"]).sort_values("count", ascending=False).head(10)
    print("\nTop 10 Destinations by Volume:")
    for dest, row in dest_rates.iterrows():
        print(f"  {dest:<20}: {row['count']:<5.0f} cases | {row['mean']:.2%} claim rate")
        
    # Duration (Bucket)
    df["Duration_Bucket"] = pd.qcut(df["Duration"], q=5, duplicates="drop")
    dur_rates = df.groupby("Duration_Bucket", observed=False)["Claim"].agg(["count", "mean"])
    print("\nDuration Quintiles:")
    for bkt, row in dur_rates.iterrows():
        print(f"  {str(bkt):<20}: {row['count']:<5.0f} cases | {row['mean']:.2%} claim rate")

if __name__ == "__main__":
    run_evaluation()
