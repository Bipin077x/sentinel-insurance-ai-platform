import json
from collections import defaultdict

def run_fairness_eval(db_session, raw_apps_file="synthetic_applications.json"):
    """
    Computes disparate-impact metrics on underwriting decisions.
    Checks for proxy correlations between model inputs (like destination) and protected groups.
    """
    
    with open(raw_apps_file, "r") as f:
        raw_apps = json.load(f)
        
    app_demographics = {}
    for app in raw_apps:
        # Ignore bad injected apps for fairness metrics, or assign them a default
        group = app.get("metadata", {}).get("demographic_group", "Unknown")
        app_demographics[app["app_id"]] = group

    from core.database import DecisionRecord, AuditTrailRecord
    
    decisions = db_session.query(DecisionRecord).filter(DecisionRecord.function_type == "underwriting").all()
    
    group_stats = defaultdict(lambda: {"total": 0, "approved": 0, "total_premium": 0.0, "premium_count": 0, "destinations": defaultdict(int)})
    
    for dec in decisions:
        app_id = dec.subject_id
        group = app_demographics.get(app_id, "Unknown")
        if group == "Unknown":
            continue
            
        group_stats[group]["total"] += 1
        
        # Consider 'accept' and 'accept-with-loading' as approved
        is_approved = dec.outcome in ["accept", "accept-with-loading"]
        if is_approved:
            group_stats[group]["approved"] += 1
            
        # Extract premium and destination from Audit Trail
        audit = db_session.query(AuditTrailRecord).filter(AuditTrailRecord.decision_id == dec.id).first()
        if audit:
            snapshot = json.loads(audit.inputs_snapshot)
            if "risk_assessment" in snapshot and snapshot["risk_assessment"]["suggested_premium"]:
                group_stats[group]["total_premium"] += snapshot["risk_assessment"]["suggested_premium"]
                group_stats[group]["premium_count"] += 1
            if "application" in snapshot and "destination" in snapshot["application"]:
                dest = snapshot["application"]["destination"]
                group_stats[group]["destinations"][dest] += 1
                
    report = {
        "groups": {},
        "disparate_impact": {},
        "proxy_correlation_flags": []
    }
    
    for group, stats in group_stats.items():
        approval_rate = (stats["approved"] / stats["total"]) if stats["total"] > 0 else 0
        avg_premium = (stats["total_premium"] / stats["premium_count"]) if stats["premium_count"] > 0 else 0
        report["groups"][group] = {
            "total_applicants": stats["total"],
            "approval_rate": approval_rate,
            "average_premium": avg_premium,
            "destinations": dict(stats["destinations"])
        }
        
    # Calculate Disparate Impact (Four-Fifths Rule)
    if "Group A" in report["groups"] and "Group B" in report["groups"]:
        rate_a = report["groups"]["Group A"]["approval_rate"]
        rate_b = report["groups"]["Group B"]["approval_rate"]
        
        if rate_a > 0:
            di_ratio = rate_b / rate_a
            report["disparate_impact"]["approval_rate_ratio_B_to_A"] = di_ratio
            if di_ratio < 0.8:
                report["disparate_impact"]["flag"] = True
                report["disparate_impact"]["message"] = f"Disparate impact detected! Group B approval rate is only {di_ratio*100:.1f}% of Group A."
            else:
                report["disparate_impact"]["flag"] = False
                
        # Check Proxy Correlation for Destinations
        # E.g., does a specific destination belong overwhelmingly to one group?
        all_dests = set()
        for g in report["groups"]:
            all_dests.update(report["groups"][g]["destinations"].keys())
            
        for dest in all_dests:
            total_dest_apps = sum(report["groups"][g]["destinations"].get(dest, 0) for g in report["groups"])
            if total_dest_apps > 0:
                count_b = report["groups"]["Group B"]["destinations"].get(dest, 0)
                prob_b_given_dest = count_b / total_dest_apps
                # If destination is mostly Group B, it could act as a proxy
                if prob_b_given_dest > 0.7:
                    report["proxy_correlation_flags"].append(
                        f"Proxy Risk: Destination '{dest}' heavily correlates with Group B ({prob_b_given_dest*100:.1f}% of applicants going here are Group B)."
                    )

    return report
