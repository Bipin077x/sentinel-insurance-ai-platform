import os
import sys
import subprocess
import json

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fairness.generate_correlated_population import generate_population
from fairness.four_fifths_eval import evaluate_run
from underwriting.run_underwriting import run_pipeline
from core.database import init_db

def run_experiment(b_share: int, a_share: int, prefix: str):
    print(f"\n=============================================")
    print(f"Running Experiment: {b_share}/{a_share} Split ({prefix})")
    print(f"=============================================")
    
    # 1. Generate correlated population
    generate_population(b_share, a_share, prefix)
    
    # 2. Run unmodified pipeline
    # The pipeline reads from synthetic_applications.json which was just updated
    # use_adapters=False to keep it quick and deterministic
    run_pipeline(use_adapters=False)
    
    # 3. Evaluate results
    res = evaluate_run(prefix)
    
    print(f"  Group A Approval Rate: {res['rate_a']:.1%}")
    print(f"  Group B Approval Rate: {res['rate_b']:.1%}")
    print(f"  Four-Fifths Ratio: {res['ratio']:.3f} (Violation: {res['is_violation']})")
    print(f"  Statistical Significance (p-value): {res['p_value']:.4f} (Significant: {res['is_significant']})")
    
    return res

def main():
    init_db()
    
    splits = [
        (60, 40, "APP-6040"),
        (75, 25, "APP-7525"),
        (90, 10, "APP-9010"),
        (50, 50, "APP-5050") # Root cause decorrelated baseline
    ]
    
    results = {}
    
    for b_share, a_share, prefix in splits:
        res = run_experiment(b_share, a_share, prefix)
        results[f"{b_share}/{a_share}"] = res
        
    print("\n\n#################################################################")
    print("# Phase 16: Emergent Proxy Bias Sensitivity Curve               #")
    print("#################################################################")
    print(f"| Correlation Split (B/A) | Four-Fifths Ratio | Violated? | Stat. Sig? (p<0.05) |")
    print(f"|-------------------------|-------------------|-----------|---------------------|")
    
    for b_share, a_share, prefix in splits:
        res = results[f"{b_share}/{a_share}"]
        ratio_str = f"{res['ratio']:.3f}"
        violated_str = "YES" if res['is_violation'] else "NO"
        sig_str = f"YES (p={res['p_value']:.4f})" if res['is_significant'] else f"NO (p={res['p_value']:.4f})"
        print(f"| {b_share}/{a_share:<17} | {ratio_str:<17} | {violated_str:<9} | {sig_str:<19} |")
        
    print("\nRoot-Cause Confirmation:")
    res_5050 = results["50/50"]
    if not res_5050["is_violation"] and not res_5050["is_significant"]:
        print("-> Confirmed: When the proxy correlation is removed (50/50), the disparity disappears.")
        print("-> The disparate impact observed at higher correlations is emergent purely from the proxy (trip_cost), not from any other unintended pathway.")
    else:
        print("-> WARNING: Disparity detected even at 50/50. There is another bias pathway in the system.")

if __name__ == "__main__":
    main()
