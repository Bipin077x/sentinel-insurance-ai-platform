import json
import sys
import os
from collections import defaultdict
from scipy.stats import chi2_contingency

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from core.reasoning_log import query_decisions

def evaluate_run(prefix: str):
    # We get all decisions from the DB where subject_id starts with prefix
    with open("synthetic_applications.json", "r") as f:
        apps = json.load(f)
        
    group_map = {app["app_id"]: app["metadata"]["demographic_group"] for app in apps if app["app_id"].startswith(prefix)}
    
    decisions = query_decisions({})
    run_decisions = [d for d in decisions if d.subject_id in group_map]
    
    group_stats = defaultdict(lambda: {"total": 0, "approved": 0, "declined": 0, "referred": 0})
    
    for d in run_decisions:
        group = group_map[d.subject_id]
        group_stats[group]["total"] += 1
        
        if d.outcome in ["accept", "accept-with-loading"] and d.status.value == "auto_decided":
            group_stats[group]["approved"] += 1
        elif d.status.value == "pending_review" or d.outcome == "refer":
            group_stats[group]["referred"] += 1
        else:
            group_stats[group]["declined"] += 1
            
    # Calculate Four Fifths
    stats_a = group_stats.get("Group A", {"total": 1, "approved": 0})
    stats_b = group_stats.get("Group B", {"total": 1, "approved": 0})
    
    rate_a = stats_a["approved"] / max(stats_a["total"], 1)
    rate_b = stats_b["approved"] / max(stats_b["total"], 1)
    
    ratio = rate_b / rate_a if rate_a > 0 else 0
    if ratio > 1.0:
        ratio = rate_a / rate_b if rate_b > 0 else 0
        
    is_violation = ratio < 0.8
    
    # Statistical significance (Chi-squared test)
    # Contingency table:
    #             Approved  |  Not Approved
    # Group A:    a_app     |  a_not
    # Group B:    b_app     |  b_not
    a_not = stats_a["total"] - stats_a["approved"]
    b_not = stats_b["total"] - stats_b["approved"]
    
    contingency_table = [
        [stats_a["approved"], a_not],
        [stats_b["approved"], b_not]
    ]
    
    chi2, p_value, _, _ = chi2_contingency(contingency_table)
    is_significant = p_value < 0.05
    
    return {
        "rate_a": rate_a,
        "rate_b": rate_b,
        "ratio": ratio,
        "is_violation": is_violation,
        "p_value": p_value,
        "is_significant": is_significant,
        "stats_a": dict(stats_a),
        "stats_b": dict(stats_b)
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python four_fifths_eval.py <prefix>")
        sys.exit(1)
        
    res = evaluate_run(sys.argv[1])
    print(json.dumps(res, indent=2))
