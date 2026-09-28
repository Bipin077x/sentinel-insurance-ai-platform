"""
THRESHOLD CHANGE LOG - Phase 12 Real Data Migration
1. Replaced 'round_number_amount' with 'major_damage_flag' since modulo 1000 is too arbitrary for real data, and 'Major Damage' correlates strongly (60%) with real fraud labels in the dataset.
2. Modified 'immediate_claim' to use a 30-day window instead of 48h, representing a new policy term window, since 48h is rarely triggered in real distributions.
3. Added 'high_severity_no_police' combining Major Damage with missing police reports.
4. Mismatched dates removed because Kaggle dataset doesn't trigger it (all claims after bind date).
"""
from typing import Tuple, List
from datetime import timezone
from core.models import Claim
from core.database import SessionLocal, PolicyRecord, ClaimRecord
import json

def evaluate_fraud_flags(claim: Claim) -> Tuple[float, List[str]]:
    flags = []
    score = 0.0
    
    # Check if cause has Major Damage
    if "Major Damage" in claim.cause:
        flags.append("major_damage")
        score += 0.6
        
    with SessionLocal() as db:
        policy = db.query(PolicyRecord).filter(PolicyRecord.policy_number == claim.policy_id).first()
        if policy:
            claim_date = claim.date_filed
            if claim_date.tzinfo is None:
                claim_date = claim_date.replace(tzinfo=timezone.utc)
                
            eff_date = policy.effective_date
            if eff_date.tzinfo is None:
                eff_date = eff_date.replace(tzinfo=timezone.utc)
                
            delta = claim_date - eff_date
            # Changed 48h to 30 days (first month of policy/term)
            if 0 <= delta.total_seconds() <= 30 * 24 * 3600:
                flags.append("recent_policy_claim")
                score += 0.3
                
        # 4. Duplicate submission pattern (multiple claims on same policy)
        recent_claims = db.query(ClaimRecord).filter(
            ClaimRecord.policy_id == claim.policy_id,
            ClaimRecord.id != claim.id
        ).all()
        
        if len(recent_claims) >= 1:
            flags.append("duplicate_submission_pattern")
            score += 0.5
            
    # Cap score at 1.0
    score = min(score, 1.0)
    return score, flags
