import json
from typing import List
from pydantic import BaseModel
from core.models import Claim, RuleResult, Decision
from core.llm_client import call_llm_with_schema

class DecisionOutput(BaseModel):
    outcome: str  # "approve", "deny", "review"
    amount_approved: float
    confidence: float
    reasoning_text: str
    cited_rules: List[str]
    cited_fields: List[str]

from core.prompt_registry import load_prompt

def make_decision(claim: Claim, rule_results: List[RuleResult], fraud_score: float, fraud_flags: List[str]) -> tuple[DecisionOutput, str]:
    """
    Combines all inputs and asks the LLM to make a judgment.
    """
    
    rules_summary = "\n".join([f"- {r.rule_name}: {'PASS' if r.passed else 'FAIL'} ({r.detail})" for r in rule_results])
    
    template, prompt_hash = load_prompt("claims_decision", "v1")
    prompt = template.replace("{{claim_id}}", claim.id) \
                     .replace("{{policy_id}}", claim.policy_id) \
                     .replace("{{date_filed}}", claim.date_filed.isoformat()) \
                     .replace("{{claim_type}}", claim.claim_type) \
                     .replace("{{amount}}", str(claim.amount)) \
                     .replace("{{cause}}", claim.cause) \
                     .replace("{{rules_summary}}", rules_summary) \
                     .replace("{{fraud_score}}", str(fraud_score)) \
                     .replace("{{fraud_flags}}", str(fraud_flags))
    
    def mock_llm_decision(p, schema):
        # We mock the LLM logic based on the inputs for the POC
        all_rules_passed = all(r.passed for r in rule_results)
        
        outcome = "approve"
        amount_approved = claim.amount
        confidence = 0.95
        reasoning = "All rules passed and no major fraud flags detected. Claim is straightforward."
        
        cited_rules = [r.rule_name for r in rule_results]
        cited_fields = ["amount", "cause", "claim_type"]
        
        if not all_rules_passed:
            outcome = "deny"
            amount_approved = 0.0
            failed_rules = [r.rule_name for r in rule_results if not r.passed]
            reasoning = f"Claim denied due to failing rules: {', '.join(failed_rules)}."
            confidence = 0.98
            cited_rules = failed_rules
            cited_fields = ["amount"]
        elif fraud_score >= 0.5:
            # Simulate non-determinism for ambiguous cases
            import random
            if random.random() < 0.6:
                outcome = "review"
                amount_approved = 0.0
                reasoning = "Fraud score is high, requires human review."
                confidence = 0.80
            else:
                outcome = "approve"
                amount_approved = claim.amount
                reasoning = "Fraud score is high but evidence seems sufficient."
                confidence = 0.60
            cited_fields = ["amount", "cause"]
            
        return json.dumps({
            "outcome": outcome,
            "amount_approved": amount_approved,
            "confidence": confidence,
            "reasoning_text": reasoning,
            "cited_rules": cited_rules,
            "cited_fields": cited_fields
        })
        
    return call_llm_with_schema(prompt, DecisionOutput, mock_llm_decision), prompt_hash
