import sys
import os
import json
from dotenv import load_dotenv

load_dotenv()
import os
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.llm_client import call_llm_with_schema, get_cost, TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS
from pydantic import BaseModel
import yaml
from core.model_registry import check_and_log_model_version

class TestSchema(BaseModel):
    message: str
    confidence: float

def test_stage0():
    # Update config to use real model
    config_path = "config/model_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "gpt-4o-2024-08-06"}, f)
        
    check_and_log_model_version()
    
    prompt = "Extract the following: The message is 'Hello world' and the confidence is 0.95."
    
    print("Making real API call...")
    try:
        # We pass a dummy mock callable that won't be used since the model is real
        result = call_llm_with_schema(prompt, TestSchema, lambda p, s: "{}")
        print(f"Raw structured output parsed successfully: {result.model_dump_json(indent=2)}")
        print(f"Tokens used: {TOTAL_INPUT_TOKENS} input, {TOTAL_OUTPUT_TOKENS} output")
        print(f"Actual cost: ${get_cost():.4f}")
    except Exception as e:
        print(f"Error during API call: {e}")
        
    # Revert config
    with open(config_path, "w") as f:
        yaml.dump({"model_id": "mock-llm-1.0-0613"}, f)

if __name__ == "__main__":
    test_stage0()
