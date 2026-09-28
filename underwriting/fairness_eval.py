import json
from collections import defaultdict
from core.reasoning_log import get_decision_trail

def evaluate_fairness():
    with open("synthetic_applications.json", "r") as f:
        apps = json.load(f)
        
    group_stats = defaultdict(lambda: {"total": 0, "approved": 0, "declined": 0, "referred": 0})
    
    # Feature correlations
    feature_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    print("--- Underwriting Fairness Evaluation (Synthetic POC) ---")
    print("WARNING: This evaluation runs against purely synthetic demographic attributes.")
    print("Production demographic sourcing (e.g., BISG inference) requires explicit legal and compliance sign-off.")
    print("--------------------------------------------------------\n")
    
    for app in apps:
        if "BAD" in app["app_id"]:
            continue
            
        app_id = app["app_id"]
        group = app["metadata"].get("demographic_group", "Unknown")
        
        # We need to extract features like destination to check correlations
        # We can just cheat a bit by parsing the raw_text since it's a simple eval script
        text = app["raw_text"].lower()
        dest = "unknown"
        if "france" in text: dest = "France"
        elif "italy" in text: dest = "Italy"
        elif "north korea" in text: dest = "North Korea"
        elif "switzerland" in text: dest = "Switzerland"
        elif "canada" in text: dest = "Canada"
        elif "usa" in text: dest = "USA"
        
        feature_counts["destination"][dest][group] += 1
        
        decision_id = f"dec_{app_id}"
        trail = get_decision_trail(decision_id)
        if not trail:
            continue
            
        outcome = trail["decision"].outcome
        status = trail["decision"].status
        
        group_stats[group]["total"] += 1
        
        # Treat accept and accept-with-loading as approved
        if outcome in ["accept", "accept-with-loading"] and status == "auto_decided":
            group_stats[group]["approved"] += 1
        elif status == "pending_review" or outcome == "refer":
            group_stats[group]["referred"] += 1
        else:
            group_stats[group]["declined"] += 1
            
    # Approval Rates
    print("Approval Rates by Demographic Group:")
    for group, stats in group_stats.items():
        total = stats["total"]
        if total > 0:
            appr_rate = stats['approved'] / total
            print(f"  {group}: {stats['approved']}/{total} ({appr_rate*100:.1f}%) | Referred: {stats['referred']} | Declined: {stats['declined']}")
            
    # Correlation Checks
    print("\nFeature Correlation Check (Proxy Bias Detection):")
    for feature, values in feature_counts.items():
        print(f"  Feature: {feature}")
        for val, group_map in values.items():
            total = sum(group_map.values())
            print(f"    {val} -> ", end="")
            for g, count in group_map.items():
                print(f"{g}: {count}/{total} ({(count/total)*100:.1f}%) | ", end="")
            print()
            
    print("\nNote: Disparate impact is considered a flag if the approval rate ratio between groups falls below 0.8 (four-fifths rule).")
    
if __name__ == "__main__":
    evaluate_fairness()
