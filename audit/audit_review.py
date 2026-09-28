import json
from pydantic import BaseModel
from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt

class AuditFinding(BaseModel):
    is_supported: bool
    inconsistencies_found: bool
    audit_rationale: str

def conduct_audit_review(decision_data: dict, anomaly_reason: str) -> tuple[AuditFinding, str]:
    """
    Uses the LLM to review a specific decision's reasoning trail.
    """
    decision = decision_data["decision"]
    audit_trail = decision_data["audit_trail"]
    
    rules_fired_str = "\n".join(decision.rules_fired) if decision.rules_fired else "None"
    
    template, prompt_hash = load_prompt("audit_review", "v1")
    prompt = template.replace("{{anomaly_reason}}", anomaly_reason) \
                     .replace("{{decision_id}}", str(decision.id)) \
                     .replace("{{function_type}}", str(decision.function_type)) \
                     .replace("{{outcome}}", str(decision.outcome)) \
                     .replace("{{confidence_score}}", str(decision.confidence_score)) \
                     .replace("{{reasoning_text}}", str(decision.reasoning_text)) \
                     .replace("{{rules_fired}}", rules_fired_str) \
                     .replace("{{inputs_snapshot}}", json.dumps(audit_trail.inputs_snapshot, indent=2)) \
                     .replace("{{rule_results}}", json.dumps(audit_trail.rule_results, indent=2))
    
    def mock_llm_audit(p, schema):
        # We mock the auditor LLM logic
        is_supported = True
        inconsistencies = False
        rationale = "The decision appears to be well-supported by the data and rules executed. The math and logic align."
        
        # Add some flavor based on anomaly reason
        if "Borderline" in anomaly_reason:
            rationale += " However, the confidence score was borderline, justifying this review. The edge case was handled correctly."
        elif "PENDING_REVIEW" in anomaly_reason:
            rationale += " The decision correctly escalated to human review due to high stakes or low confidence."
            
        return json.dumps({
            "is_supported": is_supported,
            "inconsistencies_found": inconsistencies,
            "audit_rationale": rationale
        })

    finding = call_llm_with_schema(prompt, AuditFinding, mock_llm_audit)
    return finding, prompt_hash
