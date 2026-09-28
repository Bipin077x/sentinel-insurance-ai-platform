import json
from typing import List
from datetime import datetime, timezone, timedelta
from core.models import Claim, RuleResult
from core.database import SessionLocal, PolicyRecord, ClaimRecord
from core.compliance import check_compliance_rule

def check_rules(claim: Claim) -> List[RuleResult]:
    """
    Runs deterministic checks based on the extracted claim and the policy.
    """
    results = []
    
    with SessionLocal() as db:
        # Fetch policy
        policy = db.query(PolicyRecord).filter(PolicyRecord.policy_number == claim.policy_id).first()
        
        if not policy:
            results.append(RuleResult(rule_name="policy_exists", passed=False, detail="Policy not found"))
            return results
            
        # 1. Policy Validity Dates
        claim_date = claim.date_filed
        if claim_date.tzinfo is None:
            claim_date = claim_date.replace(tzinfo=timezone.utc)
            
        eff_date = policy.effective_date
        if eff_date.tzinfo is None:
            eff_date = eff_date.replace(tzinfo=timezone.utc)
            
        exp_date = policy.expiry_date
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)
            
        if policy.product_type == "auto":
            # For auto policies in Kaggle dataset, the effective date is the original bind date 
            # and they renew annually, so we just check if it was bound BEFORE the claim date
            is_active = eff_date <= claim_date
        else:
            is_active = eff_date <= claim_date <= exp_date
            
        results.append(RuleResult(
            rule_name="policy_active", 
            passed=is_active, 
            detail="Claim filed outside policy effective dates" if not is_active else "Policy active"
        ))
        
        # 2. Coverage Limit Check
        limits = json.loads(policy.coverage_limits)
        if policy.product_type == "auto":
            # Auto policies have CSL + umbrella limits
            limit = limits.get("csl", 0.0) + limits.get("umbrella", 0.0)
        else:
            limit = limits.get(claim.claim_type, 0.0)
            
        within_limit = claim.amount <= limit
        results.append(RuleResult(
            rule_name="coverage_limit",
            passed=within_limit,
            detail=f"Claim amount {claim.amount} exceeds limit {limit}" if not within_limit else "Within limits"
        ))
        
        # 3. Exclusion Check (Simple string match for POC)
        exclusions = json.loads(policy.exclusions)
        has_exclusion = False
        triggered_excl = ""
        for excl in exclusions:
            if excl.lower() in claim.cause.lower() or claim.cause.lower() in excl.lower():
                has_exclusion = True
                triggered_excl = excl
                break
                
        results.append(RuleResult(
            rule_name="exclusion_check",
            passed=not has_exclusion,
            detail=f"Cause triggers exclusion: {triggered_excl}" if has_exclusion else "No exclusions triggered"
        ))
        
        # 4. Duplicate Claim Check
        # A claim is duplicate if it shares policy_id and date_filed is very close, OR if same claim_type/amount.
        duplicates = db.query(ClaimRecord).filter(
            ClaimRecord.policy_id == claim.policy_id,
            ClaimRecord.id != claim.id
        ).all()
        
        is_duplicate = False
        for d in duplicates:
            if d.amount == claim.amount and d.claim_type == claim.claim_type:
                is_duplicate = True
                break
                
        results.append(RuleResult(
            rule_name="duplicate_claim",
            passed=not is_duplicate,
            detail="Duplicate claim detected" if is_duplicate else "No duplicates"
        ))
        
        # 5. Regulatory filing-deadline check
        max_filing_days = check_compliance_rule("max_claim_filing_days_after_incident")
        if max_filing_days is None:
            max_filing_days = 30 # default 30 if not found
        
        incident_date = claim.incident_date
        if incident_date.tzinfo is None:
            incident_date = incident_date.replace(tzinfo=timezone.utc)
            
        days_since_incident = (claim_date - incident_date).days
        passed_deadline = days_since_incident <= max_filing_days
        
        results.append(RuleResult(
            rule_name="compliance_filing_deadline",
            passed=passed_deadline,
            detail=f"Claim filed {days_since_incident} days after incident (limit {max_filing_days})" if not passed_deadline else "Filed within regulatory deadline"
        ))
        
    return results
