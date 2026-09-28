from typing import List, Dict, Any

def generate_report(total_reviewed: int, audit_results: List[Dict[str, Any]]):
    print("\n" + "="*50)
    print("FINANCIAL AUDIT REPORT")
    print("="*50)
    print(f"Total Decisions Scanned: {total_reviewed}")
    print(f"Total Anomalies Flagged for LLM Review: {len(audit_results)}")
    
    inconsistencies = 0
    unsupported = 0
    
    for res in audit_results:
        finding = res["finding"]
        if finding.inconsistencies_found:
            inconsistencies += 1
        if not finding.is_supported:
            unsupported += 1
            
    print("\n--- Summary of LLM Audit Findings ---")
    print(f"Decisions Unsupported by Rules/Data: {unsupported}")
    print(f"Decisions with Logical Inconsistencies: {inconsistencies}")
    print(f"Decisions Verified as Correct: {len(audit_results) - unsupported - inconsistencies}")
    
    print("\n--- Detailed Follow-ups ---")
    for res in audit_results:
        print(f"Target Decision: {res['target_decision_id']}")
        print(f"  Anomaly Reason: {res['anomaly_reason']}")
        print(f"  Auditor Rationale: {res['finding'].audit_rationale}\n")
    print("="*50 + "\n")
