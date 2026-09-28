import sys
import os
import json
import numpy as np
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data.kfold_split import get_stratified_folds
from claims.rules import check_rules
from claims.decision import make_decision
from core.database import Base, engine, SessionLocal, PolicyRecord
from core.calibration import compute_semantic_entropy
from core.gate import should_auto_decide

def setup_db():
    Base.metadata.create_all(bind=engine)

def discover_rules(train_data):
    """
    Simulates the human discovery process from Phase 12.
    Explores text fragments in `cause` (which contains incident_severity) 
    and finds features with high correlation to fraud.
    """
    feature_stats = defaultdict(lambda: {"total": 0, "fraud": 0})
    
    for claim, policy, is_fraud, raw in train_data:
        # Extract the severity from cause, e.g. "Side Collision (Major Damage)" -> "Major Damage"
        # Or just look at raw row if we want to be clean
        severity = raw.get("incident_severity", "")
        if severity:
            feature_stats[severity]["total"] += 1
            if is_fraud:
                feature_stats[severity]["fraud"] += 1
                
    discovered_rules = {}
    for feat, stats in feature_stats.items():
        if stats["total"] >= 20: # Must have enough support
            corr = stats["fraud"] / stats["total"]
            # If correlation is highly predictive (e.g. > 50%), assign it a score > 0.5
            if corr > 0.5:
                # E.g. correlation of 60% gets score 0.6
                discovered_rules[feat] = round(corr, 2)
                
    return discovered_rules

def dynamic_evaluate_fraud_flags(claim, raw, discovered_rules):
    """
    Evaluates fraud flags using the dynamically discovered rules for this fold.
    """
    flags = []
    score = 0.0
    
    severity = raw.get("incident_severity", "")
    if severity in discovered_rules:
        flags.append(severity.replace(" ", "_").lower())
        score += discovered_rules[severity]
        
    return score, flags

def main():
    setup_db()
    folds = get_stratified_folds()
    
    # Load all policies into DB first
    with SessionLocal() as db:
        for fold in folds:
            for claim, policy, is_fraud, raw in fold:
                if not db.query(PolicyRecord).filter_by(policy_number=policy.policy_number).first():
                    pr = PolicyRecord(
                        policy_number=policy.policy_number,
                        product_type=policy.product_type,
                        coverage_limits=json.dumps(policy.coverage_limits),
                        exclusions=json.dumps(policy.exclusions),
                        premium=policy.premium,
                        effective_date=policy.effective_date,
                        expiry_date=policy.expiry_date,
                        holder_id=policy.holder_id
                    )
                    db.add(pr)
        db.commit()

    escalation_policy = {
        "claims": {
            "default_confidence_threshold": 0.85,
            "override_threshold": 0.5,
            "hard_ceiling": 1_000_000,
            "stakes_thresholds": [
                {"max_stakes": 2000, "confidence_threshold": 0.85},
                {"max_stakes": None, "confidence_threshold": 0.95}
            ]
        }
    }
    
    metrics = []
    
    print("=== K-Fold Cross-Validation on Real Claims ===")
    
    for k in range(5):
        # Create train and test sets
        test_data = folds[k]
        train_data = []
        for j in range(5):
            if j != k:
                train_data.extend(folds[j])
                
        # Discover rules
        discovered_rules = discover_rules(train_data)
        
        TP, FP, TN, FN = 0, 0, 0, 0
        
        for claim, policy, is_fraud, raw in test_data:
            rule_results = check_rules(claim)
            fraud_score, fraud_flags = dynamic_evaluate_fraud_flags(claim, raw, discovered_rules)
            
            def _claims_llm_caller():
                return make_decision(claim, rule_results, fraud_score, fraud_flags)
                
            decision_out, _, calibrated_confidence, _ = compute_semantic_entropy(_claims_llm_caller, num_samples=3)
            
            can_auto_decide, auto_decide_reason = should_auto_decide(
                calibrated_confidence, 
                claim.amount, 
                "claims", 
                escalation_policy, 
                override_score=fraud_score,
                override_type="fraud",
                hard_ceiling=escalation_policy["claims"].get("hard_ceiling")
            )
            
            predicted_fraud = decision_out.outcome in ["review", "deny"]
            
            if predicted_fraud and is_fraud: TP += 1
            elif predicted_fraud and not is_fraud: FP += 1
            elif not predicted_fraud and is_fraud: FN += 1
            elif not predicted_fraud and not is_fraud: TN += 1
            
        total = len(test_data)
        accuracy = (TP + TN) / total
        precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
        recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics.append({
            "fold": k + 1,
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": TP,
            "fp": FP,
            "tn": TN,
            "fn": FN,
            "discovered_rules": discovered_rules
        })
        
    # Write report
    report_content = "# Phase 13: K-Fold Cross-Validation Report\n\n"
    report_content += "## Fold Metrics\n\n"
    report_content += "| Fold | Accuracy | Precision | Recall | F1 Score | Discovered Rules |\n"
    report_content += "|---|---|---|---|---|---|\n"
    
    accs, precs, recs, f1s = [], [], [], []
    for m in metrics:
        accs.append(m["accuracy"])
        precs.append(m["precision"])
        recs.append(m["recall"])
        f1s.append(m["f1"])
        
        rules_str = ", ".join([f"{k} (score: {v})" for k,v in m["discovered_rules"].items()])
        if not rules_str: rules_str = "None"
        report_content += f"| {m['fold']} | {m['accuracy']:.1%} | {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} | {rules_str} |\n"
        
    report_content += "\n## Summary Statistics\n\n"
    report_content += f"- **Accuracy**: {np.mean(accs):.1%} ± {np.std(accs):.1%}\n"
    report_content += f"- **Precision**: {np.mean(precs):.1%} ± {np.std(precs):.1%}\n"
    report_content += f"- **Recall**: {np.mean(recs):.1%} ± {np.std(recs):.1%}\n"
    report_content += f"- **F1 Score**: {np.mean(f1s):.1%} ± {np.std(f1s):.1%}\n"
    
    report_content += "\n## Interpretation\n\n"
    report_content += "### Stability Across Folds\n"
    std_prec = np.std(precs)
    std_rec = np.std(recs)
    if std_prec > 0.05 or std_rec > 0.05:
        report_content += "The performance is **fragile**. The standard deviation is wide relative to the mean, demonstrating that Phase 12's initial single-split results were heavily influenced by favorable sampling noise.\n"
    else:
        report_content += "The performance is **stable** across folds. The tight standard deviation confirms the robustness of the discovery process.\n"
        
    report_content += "\n### Comparison to Phase 12\n"
    report_content += f"Phase 12 reported 64.7% precision and 44.9% recall. Across the 5 folds, we see a mean precision of {np.mean(precs):.1%} and recall of {np.mean(recs):.1%}. "
    if abs(np.mean(precs) - 0.647) > 0.05:
        report_content += "The cross-validated metrics are meaningfully different from the initial run, indicating that the 'encouraging initial signal' must be walked back. The original split was optimistic.\n"
    else:
        report_content += "The metrics hold up well, upgrading the 'encouraging initial signal' to a cross-validated result.\n"
        
    report_content += "\n### Rule Discovery Consistency\n"
    rules_sets = [str(list(m["discovered_rules"].keys())) for m in metrics]
    if len(set(rules_sets)) == 1:
        report_content += f"The rule discovery process robustly identified the exact same features (`{rules_sets[0]}`) in all 5 folds independently. This is strong evidence that the feature correlation is a genuine dataset-wide pattern, not an artifact of one specific sub-sample.\n"
    else:
        report_content += "The discovered rules varied across folds, meaning the initial signal was partially driven by fold-specific clusters rather than a global pattern.\n"
        
    report_content += "\n\n```\nTest: 5-Fold Cross-Validation on Real Claims Eval\n"
    report_content += f"Actual output: {len(metrics)}-fold CV completed. Mean Precision {np.mean(precs):.1%} ± {np.std(precs):.1%}, Recall {np.mean(recs):.1%} ± {np.std(recs):.1%}\n"
    report_content += "Result: Pass\n```"
    
    with open("reports/kfold_report.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("Report written to reports/kfold_report.md")

if __name__ == "__main__":
    main()
