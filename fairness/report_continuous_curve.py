import os
import sys
import subprocess
import json

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fairness.generate_continuous_population import generate_population
from fairness.four_fifths_eval import evaluate_run
from underwriting.run_underwriting import run_pipeline
from core.database import init_db

def run_experiment(b_share: int, a_share: int, prefix: str):
    print(f"\n=============================================")
    print(f"Running Experiment: {b_share}/{a_share} Continuous Shift ({prefix})")
    print(f"=============================================")
    
    # 1. Generate population
    generate_population(b_share, a_share, prefix)
    
    # 2. Naive Prediction Check
    # Since risk_scoring uses age > 50 as a discrete threshold (when combined with pre-existing conditions),
    # anyone with age > 50 will hit High Risk (multiplier 1.95) and fail the gate or be declined/referred.
    with open("synthetic_applications.json", "r") as f:
        apps = json.load(f)
    
    naive_a_total = 0
    naive_a_approved = 0
    naive_b_total = 0
    naive_b_approved = 0
    
    for app in apps:
        if not app["app_id"].startswith(prefix):
            continue
        group = app["metadata"]["demographic_group"]
        age = app["age"]
        # Naive prediction: age <= 50 will be approved, age > 50 will be non-approved
        approved = age <= 50
        
        if group == "Group A":
            naive_a_total += 1
            if approved: naive_a_approved += 1
        else:
            naive_b_total += 1
            if approved: naive_b_approved += 1
            
    naive_rate_a = naive_a_approved / max(1, naive_a_total)
    naive_rate_b = naive_b_approved / max(1, naive_b_total)
    naive_ratio = naive_rate_b / naive_rate_a if naive_rate_a > 0 else 0
    
    print(f"\n[Naive Prediction Based ONLY on age <= 50 Threshold]")
    print(f"  Group A Naive Rate: {naive_rate_a:.1%}")
    print(f"  Group B Naive Rate: {naive_rate_b:.1%}")
    print(f"  Naive Four-Fifths Ratio: {naive_ratio:.3f}")
    
    # 3. Run Pipeline
    run_pipeline(use_adapters=False)
    
    # 4. Evaluate actuals
    res = evaluate_run(prefix)
    
    print(f"\n[Actual Pipeline Execution]")
    print(f"  Group A Actual Rate: {res['rate_a']:.1%}")
    print(f"  Group B Actual Rate: {res['rate_b']:.1%}")
    print(f"  Actual Four-Fifths Ratio: {res['ratio']:.3f}")
    
    # Check if they match exactly
    if abs(naive_ratio - res['ratio']) < 0.001:
        print("  -> WARNING: The naive prediction and actual output match exactly. This means the continuous variable (age) is acting strictly as a step-function threshold inside the pipeline.")
    else:
        print("  -> SUCCESS: The naive prediction and actual output differ, proving complex continuous interaction.")
        
    return res

def main():
    init_db()
    
    splits = [
        (60, 40, "CONT-6040"),
        (75, 25, "CONT-7525"),
        (90, 10, "CONT-9010"),
        (50, 50, "CONT-5050")
    ]
    
    results = {}
    
    for b_share, a_share, prefix in splits:
        res = run_experiment(b_share, a_share, prefix)
        results[f"{b_share}/{a_share}"] = res
        
    print("\n\n#################################################################")
    print("# Phase 16b: Continuous Shift Proxy Bias Sensitivity Curve      #")
    print("#################################################################")
    print(f"| Correlation Shift (B/A) | Four-Fifths Ratio | Violated? | Stat. Sig? (p<0.05) |")
    print(f"|-------------------------|-------------------|-----------|---------------------|")
    
    for b_share, a_share, prefix in splits:
        res = results[f"{b_share}/{a_share}"]
        ratio_str = f"{res['ratio']:.3f}"
        violated_str = "YES" if res['is_violation'] else "NO"
        sig_str = f"YES (p={res['p_value']:.4f})" if res['is_significant'] else f"NO (p={res['p_value']:.4f})"
        print(f"| {b_share}/{a_share:<17} | {ratio_str:<17} | {violated_str:<9} | {sig_str:<19} |")
        
if __name__ == "__main__":
    main()
