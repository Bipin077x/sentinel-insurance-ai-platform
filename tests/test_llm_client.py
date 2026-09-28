import pytest
import json
from pydantic import BaseModel
from core.llm_client import call_llm_with_schema, LLMValidationError

class SampleSchema(BaseModel):
    name: str
    age: int

def test_llm_client_success():
    def mock_llm_success(prompt, schema_dict):
        return json.dumps({"name": "Alice", "age": 30})
        
    result = call_llm_with_schema("Tell me about Alice", SampleSchema, mock_llm_success)
    assert result.name == "Alice"
    assert result.age == 30

def test_llm_client_retry_success():
    calls = []
    
    def mock_llm_retry(prompt, schema_dict):
        calls.append(prompt)
        if len(calls) == 1:
            # First attempt: invalid output (age is string instead of int)
            return json.dumps({"name": "Bob", "age": "thirty"})
        else:
            # Second attempt: valid output
            return json.dumps({"name": "Bob", "age": 30})
            
    result = call_llm_with_schema("Tell me about Bob", SampleSchema, mock_llm_retry, max_retries=1)
    
    assert result.name == "Bob"
    assert result.age == 30
    assert len(calls) == 2
    # Ensure error was fed back into prompt
    assert "Your previous response failed validation with the following error" in calls[1]

def test_llm_client_failure():
    def mock_llm_failure(prompt, schema_dict):
        # Always returns invalid JSON
        return "Not a json string"
        
    with pytest.raises(LLMValidationError) as exc:
        call_llm_with_schema("Failing prompt", SampleSchema, mock_llm_failure, max_retries=1)
        
    assert "Failed to generate valid output after 2 attempts" in str(exc.value)
    assert "JSONDecodeError" in str(exc.value)
