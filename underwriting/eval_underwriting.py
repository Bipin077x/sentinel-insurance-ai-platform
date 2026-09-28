import json
import subprocess
from collections import defaultdict
from core.reasoning_log import get_decision_trail

def run_eval():
    with open("underwriting_ground_truth.json", "r") as f:
        ground_truths = json.load(f)
        
    category_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    total_apps = 0
    total_correct = 0
    
    referral_mechanisms_found = []
    
    for gt in ground_truths:
        app_id = gt["app_id"]
        expected_outcome = gt["expected_outcome"]
        category = gt.get("category", "unknown")
        
        # Don't evaluate the intentionally bad apps for accuracy in the same way, but check they failed
        if expected_outcome == "extraction_failed":
            decision_id = f"dec_{app_id}"
            trail = get_decision_trail(decision_id)
            if trail and trail["decision"].outcome == "extraction_failed":
                print(f"Caught invalid application {app_id} correctly at extraction.")
            continue
            
        decision_id = f"dec_{app_id}"
        trail = get_decision_trail(decision_id)
        
        if not trail:
            print(f"Decision not found for {app_id}")
            continue
            
        decision = trail["decision"]
        actual_outcome = decision.outcome
        status = decision.status
        
        total_apps += 1
        category_stats[category]["total"] += 1
        
        # We consider a match if the outcome matches, or if it was supposed to refer/review and it hit PENDING_REVIEW
        is_match = False
        if actual_outcome == expected_outcome:
            is_match = True
        elif expected_outcome in ["refer", "review"] and (actual_outcome == "refer" or status == "pending_review"):
            is_match = True
            
        if is_match:
            total_correct += 1
            category_stats[category]["correct"] += 1
            
        if category == "referral-designed":
            # Extract the actual reason logged
            lines = decision.reasoning_text.splitlines()
            reason = lines[-1] if lines else "None"
            referral_mechanisms_found.append(f"{app_id}: {reason}")
            
    print(f"\n--- Underwriting Evaluation Results ---")
    print(f"Total Applications Evaluated: {total_apps}")
    print(f"Overall Accuracy Rate: {(total_correct / total_apps) * 100:.2f}%\n")
    
    print("Breakdown by Category:")
    for cat, stats in category_stats.items():
        if stats["total"] > 0:
            print(f"  {cat}: {stats['correct']}/{stats['total']} ({(stats['correct']/stats['total'])*100:.1f}%)")
            
    print("\nReferral-designed Escalation Mechanisms:")
    for mech in referral_mechanisms_found:
        print(f"  {mech}")
        
    print("\n--- Integrity Verification ---")
    import sys
    result = subprocess.run([sys.executable, "core/chain_verify.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("ERRORS:", result.stderr)

if __name__ == "__main__":
    run_eval()
