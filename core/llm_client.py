import json
import os
import time
from typing import Type, TypeVar, Callable, Any
from pydantic import BaseModel, ValidationError

T = TypeVar('T', bound=BaseModel)

class LLMValidationError(Exception):
    """Raised when the LLM output fails to validate against the provided Pydantic schema."""
    pass

class LLMProviderError(Exception):
    """Raised when the real API fails after retries."""
    pass

# Simple cost tracking globals
TOTAL_INPUT_TOKENS = 0
TOTAL_OUTPUT_TOKENS = 0

def get_cost():
    # OpenAI gpt-4o-2024-08-06 prices: $2.50 / 1M input, $10.00 / 1M output
    in_cost = (TOTAL_INPUT_TOKENS / 1_000_000) * 2.50
    out_cost = (TOTAL_OUTPUT_TOKENS / 1_000_000) * 10.00
    return in_cost + out_cost

def _call_real_llm(prompt: str, schema_dict: dict, max_retries: int = 3) -> str:
    from openai import OpenAI
    import openai
    from core.model_registry import get_active_model
    
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "mock_key_will_fail"))
    model = get_active_model()
    
    attempts = 0
    backoff = 2.0
    
    while attempts <= max_retries:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": schema_dict,
                        "strict": True
                    }
                },
                timeout=30.0
            )
            
            global TOTAL_INPUT_TOKENS, TOTAL_OUTPUT_TOKENS
            if response.usage:
                TOTAL_INPUT_TOKENS += response.usage.prompt_tokens
                TOTAL_OUTPUT_TOKENS += response.usage.completion_tokens
                
            return response.choices[0].message.content
            
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            attempts += 1
            if attempts > max_retries:
                raise LLMProviderError(f"API unavailable after {max_retries} retries: {str(e)}")
            time.sleep(backoff)
            backoff *= 2
        except Exception as e:
            raise LLMProviderError(f"Unhandled API error: {str(e)}")
            
    raise LLMProviderError("Failed to call real LLM.")

def call_llm_with_schema(
    prompt: str, 
    schema_model: Type[T], 
    llm_callable: Callable[[str, dict], str],
    max_retries: int = 1
) -> T:
    """
    Calls an LLM and validates the output against a Pydantic schema.
    """
    from core.model_registry import get_active_model
    schema_dict = schema_model.model_json_schema()
    
    # Clean up schema for OpenAI strict mode
    if "title" in schema_dict: del schema_dict["title"]
    def _clean_schema(s):
        if "title" in s: del s["title"]
        if "additionalProperties" not in s and s.get("type") == "object":
            s["additionalProperties"] = False
        for k, v in s.items():
            if isinstance(v, dict): _clean_schema(v)
            elif isinstance(v, list): 
                for item in v:
                    if isinstance(item, dict): _clean_schema(item)
    _clean_schema(schema_dict)
    
    active_model = get_active_model()
    
    attempts = 0
    last_error = None
    
    while attempts <= max_retries:
        current_prompt = prompt
        if attempts > 0 and last_error:
            current_prompt += f"\n\nYour previous response failed validation with the following error:\n{last_error}\nPlease correct it and ensure the output strictly matches the schema."
            
        if active_model.startswith("mock-llm"):
            raw_response = llm_callable(current_prompt, schema_dict)
        else:
            try:
                raw_response = _call_real_llm(current_prompt, schema_dict)
            except LLMProviderError as e:
                # If API fails, we must fail closed (escalate) by raising here.
                # The caller will handle it or we raise a clear error that the pipeline can catch.
                raise e
        
        try:
            parsed_json = json.loads(raw_response)
            validated_data = schema_model(**parsed_json)
            return validated_data
            
        except json.JSONDecodeError as e:
            last_error = f"JSONDecodeError: {str(e)}"
        except ValidationError as e:
            last_error = f"ValidationError: {str(e)}"
        except Exception as e:
            last_error = f"Unexpected Error: {str(e)}"
            
        attempts += 1
        
    raise LLMValidationError(f"Failed to generate valid output after {max_retries + 1} attempts. Last error: {last_error}")
