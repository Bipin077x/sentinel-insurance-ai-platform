import json
from core.reasoning_log import get_decision_trail
import subprocess
import sys

def evaluate():
    with open("brokerage_ground_truth.json", "r") as f:
        ground_truths = json.load(f)
        
    correct = 0
    total = len(ground_truths)
    
    for gt in ground_truths:
        client_id = gt["client_id"]
        rec_id = f"dec_{client_id}"
        trail = get_decision_trail(rec_id)
        
        if not trail:
            print(f"[FAIL] {client_id}: No decision trail found.")
            continue
            
        case_type = gt.get("type", "unknown")
        
        if case_type == "bad":
            if trail["decision"].outcome == "extraction_failed":
                print(f"[PASS] {client_id} (Bad Data): Successfully rejected via extraction validation.")
                correct += 1
            else:
                print(f"[FAIL] {client_id} (Bad Data): Expected extraction failure, got {trail['decision'].outcome}")
            continue
            
        decision = trail["decision"]
        audit = trail["audit_trail"]
        
        if decision.outcome != "recommendation":
            print(f"[FAIL] {client_id} ({case_type}): Expected recommendation outcome, got {decision.outcome}")
            continue
            
        recommended = audit.rule_results.get("recommended", "UNKNOWN")
        expected_set = gt["expected_recommendation"]
        
        if case_type in ["clear-fit", "filter"]:
            if recommended in expected_set:
                pass_check = True
                msg = f"Match {recommended}"
                
                # For filter cases, explicitly verify the excluded product was caught by the filter
                if case_type == "filter":
                    excluded_target = gt["excluded"]
                    excluded_log = audit.rule_results.get("excluded", {})
                    if excluded_target not in excluded_log:
                        pass_check = False
                        msg = f"Failed to filter {excluded_target}. Filter log: {excluded_log}"
                    else:
                        msg += f" (Correctly filtered {excluded_target})"
                        
                if pass_check:
                    print(f"[PASS] {client_id} ({case_type}): {msg}")
                    correct += 1
                else:
                    print(f"[FAIL] {client_id} ({case_type}): {msg}")
            else:
                print(f"[FAIL] {client_id} ({case_type}): Recommended {recommended}, expected {expected_set}")
                
        elif case_type == "ambiguous":
            if recommended in expected_set:
                label = audit.inputs_snapshot.get("consistency_label", "UNKNOWN")
                print(f"[PASS] {client_id} ({case_type}): Recommended {recommended} (in acceptable set). Label: {label}")
                correct += 1
            else:
                print(f"[FAIL] {client_id} ({case_type}): Recommended {recommended} NOT in {expected_set}")
                
    print(f"\nBrokerage Accuracy: {(correct/total)*100:.2f}% ({correct}/{total})")
    
    print("\nRunning cryptographic chain verification...")
    try:
        subprocess.run([sys.executable, "core/chain_verify.py"], check=True)
    except subprocess.CalledProcessError:
        print("Chain verification failed!")

if __name__ == "__main__":
    evaluate()
