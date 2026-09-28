from typing import List, Dict, Any

def verify_faithfulness(
    cited_rules: List[str], 
    cited_fields: List[str], 
    actual_rules_fired: List[str], 
    extracted_data_keys: List[str],
    outcome: str = None,
    reasoning_text: str = None
) -> List[str]:
    """
    Verifies that the LLM's citations match the actual facts of the case.
    Also verifies coherence between the reasoning text and the outcome.
    Returns a list of fabrication errors if hallucinations or incoherence are detected.
    """
    errors = []
    
    # 1. Verify cited rules actually fired or were evaluated
    actual_rules_set = set(r.lower() for r in actual_rules_fired)
    cited_rules_set = set(r.lower() for r in cited_rules)
    
    fabricated_rules = cited_rules_set - actual_rules_set
    for rule in fabricated_rules:
        errors.append(f"Fabrication detected: cited rule '{rule}' was not evaluated for this case.")
            
    # 2. Verify cited fields actually exist in the extracted data schema
    extracted_keys_set = set(k.lower() for k in extracted_data_keys)
    cited_fields_set = set(f.lower() for f in cited_fields)
    
    fabricated_fields = cited_fields_set - extracted_keys_set
    for field in fabricated_fields:
        errors.append(f"Fabrication detected: cited field '{field}' does not exist in the extracted data.")
        
    # 3. Coherence Check: Verify outcome is reflected in the reasoning
    if outcome and reasoning_text:
        # e.g., if outcome is 'prod_adventure', ensure it's in the reasoning
        if outcome.lower() not in reasoning_text.lower():
            errors.append(f"Coherence failure: Outcome '{outcome}' is not supported or mentioned in the reasoning text.")
            
    return errors
