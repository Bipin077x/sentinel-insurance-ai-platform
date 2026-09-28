import json
from typing import List
from pydantic import BaseModel
from core.models import Application, RuleResult, Decision, FunctionType, DecisionStatus
from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt

class UnderwritingDecisionOutput(BaseModel):
    outcome: str  # "accept", "decline", "refer"
    final_premium: float
    confidence: float
    reasoning_text: str
    cited_rules: List[str]
    cited_fields: List[str]

def make_underwriting_decision(
    app: Application,
    rule_results: List[RuleResult],
    risk_tier: str,
    suggested_premium: float,
    narrative: str
) -> tuple[UnderwritingDecisionOutput, str]:
    """
    Combines all inputs and asks the LLM to make an underwriting judgment.
    """
    
    rules_summary = "\n".join([f"- {r.rule_name}: {'Passed' if r.passed else 'FAILED'} ({r.detail})" for r in rule_results])
    
    template, prompt_hash = load_prompt("underwriting_decision", "v1")
    prompt = template.replace("{{app_id}}", app.id) \
                     .replace("{{age}}", str(app.age)) \
                     .replace("{{destination}}", app.destination) \
                     .replace("{{trip_cost}}", str(app.trip_cost)) \
                     .replace("{{pre_existing_conditions}}", str(app.pre_existing_conditions)) \
                     .replace("{{activities}}", ', '.join(app.planned_activities)) \
                     .replace("{{rules_summary}}", rules_summary) \
                     .replace("{{risk_tier}}", risk_tier) \
                     .replace("{{suggested_premium}}", str(suggested_premium)) \
                     .replace("{{narrative}}", narrative)
    
    def mock_llm_decision(p, schema):
        all_rules_passed = all(r.passed for r in rule_results)
        
        cited_rules = [r.rule_name for r in rule_results]
        cited_fields = ["age", "destination", "trip_cost"]
        
        if not all_rules_passed:
            outcome = "decline"
            final_premium = 0.0
            confidence = 0.99
            failed_rules = [r.rule_name for r in rule_results if not r.passed]
            reasoning = f"Application declined due to failing eligibility rules: {', '.join(failed_rules)}."
            cited_rules = failed_rules
            cited_fields = ["age", "pre_existing_conditions"]
        elif risk_tier == "Low":
            outcome = "accept"
            final_premium = suggested_premium
            confidence = 0.95
            reasoning = "Standard risk profile, accepted at base premium."
        elif risk_tier == "Medium":
            outcome = "accept"
            final_premium = suggested_premium
            confidence = 0.90
            reasoning = "Elevated risk profile, accepted with loaded premium."
            cited_fields = ["age", "destination", "planned_activities"]
        else: # High
            # Simulate non-determinism for ambiguous cases
            import random
            if random.random() < 0.6:
                outcome = "refer"
                final_premium = suggested_premium
                confidence = 0.85
                reasoning = "High risk profile, requires human referral to price accurately."
            else:
                outcome = "decline"
                final_premium = 0.0
                confidence = 0.70
                reasoning = "High risk profile, deemed too risky to accept."
            cited_fields = ["destination", "planned_activities"]
            
        return json.dumps({
            "outcome": outcome,
            "final_premium": final_premium,
            "confidence": confidence,
            "reasoning_text": reasoning,
            "cited_rules": cited_rules,
            "cited_fields": cited_fields
        })
        
    return call_llm_with_schema(prompt, UnderwritingDecisionOutput, mock_llm_decision), prompt_hash
