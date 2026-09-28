import sys
from dotenv import load_dotenv
load_dotenv()
import os
import yaml

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.model_registry import check_and_log_model_version
from core.llm_client import get_cost, TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS
from tests.test_faithfulness import test_verify_faithfulness_fabrication
from claims.decision import make_decision
from claims.extraction import extract_claims_info
from core.models import Claim, RuleResult

def test_spontaneous_fabrication():
    """Does a real model, prompted normally, ever spontaneously cite something it shouldn't?"""
    # Create a normal clear claim
    from datetime import datetime
    claim = Claim(id="test1", policy_id="P1", date_filed=datetime.now(), claim_type="medical", amount=100.0, cause="Slip and fall")
    rules = [RuleResult(rule_name="Standard Coverage", passed=True, detail="Covered")]
    
    # We call decision which uses LLM
    decision_out, _ = make_decision(claim, rules, 0.1, [])
    
    # Check if cited rules/fields are within the provided context
    valid_rules = ["Standard Coverage"]
    valid_fields = ["amount", "cause", "claim_type", "date_filed", "id", "policy_id"]
    
    fabricated_rules = [r for r in decision_out.cited_rules if r not in valid_rules]
    fabricated_fields = [f for f in decision_out.cited_fields if f not in valid_fields]
    
    print(f"Spontaneous fabrication check:")
    print(f"  Fabricated rules: {fabricated_rules}")
    print(f"  Fabricated fields: {fabricated_fields}")
    if fabricated_rules or fabricated_fields:
        print("  WARNING: The real LLM spontaneously fabricated citations!")
    else:
        print("  PASS: No spontaneous fabrication.")

def test_out_of_bounds_extraction():
    """Confirm validators catch bad values from a real model's extraction."""
    # We provide a prompt that might trick the LLM, or we just rely on Pydantic to catch it.
    # In extraction, there are strict fields. We will pass a document that has values outside bounds (e.g. amount="one million dollars" instead of a number, or date="yesterday").
    doc_text = "The claimant wants ONE MILLION DOLLARS for an incident that happened yesterday. Type of claim: unknown_nonsense."
    try:
        result, _ = extract_claims_info(doc_text)
        print(f"Extraction result: {result}")
        print("  WARNING: The real model successfully extracted, bypassing validation? Or it coerced the data.")
    except Exception as e:
        print(f"  PASS: Extraction failed/caught as expected: {e}")

def test_stage1():
    config_path = "config/model_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "gpt-4o-2024-08-06"}, f)
        
    check_and_log_model_version()
    
    print("Running Stage 1 Adversarial Tests on Real LLM...")
    
    try:
        print("\n--- Test: Fabricated Citation Checker (Logic check) ---")
        test_verify_faithfulness_fabrication()
        print("  PASS: Checker logic correctly caught handcrafted fabrication.")
        
        print("\n--- Test: Real Model Spontaneous Fabrication ---")
        test_spontaneous_fabrication()
        
        print("\n--- Test: Out of Bounds Extraction ---")
        test_out_of_bounds_extraction()
        
    except Exception as e:
        print(f"Test failure or API error: {e}")
        
    print(f"\nTotal Tokens used in Stage 1: {TOTAL_INPUT_TOKENS} input, {TOTAL_OUTPUT_TOKENS} output")
    print(f"Total Stage 1 cost: ${get_cost():.4f}")

    # Revert config
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "mock-llm-1.0-0613"}, f)

if __name__ == "__main__":
    test_stage1()
