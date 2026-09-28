from typing import Callable, Any, Tuple

def compute_semantic_entropy(llm_caller: Callable[[], Tuple[Any, str]], num_samples: int = 5) -> Tuple[Any, str, float, str]:
    """
    Runs an LLM caller multiple times to compute semantic consistency.
    
    Args:
        llm_caller: A function that takes no arguments and returns (PydanticModel, prompt_hash)
        num_samples: Number of times to run the LLM caller
        
    Returns:
        Tuple containing:
        - The majority Pydantic model (with the modal outcome)
        - The prompt hash used
        - The computed agreement rate (0.0 to 1.0)
        - The confidence source string
    """
    if num_samples < 1:
        raise ValueError("num_samples must be at least 1")
        
    results = []
    
    for _ in range(num_samples):
        model, prompt_hash = llm_caller()
        results.append((model, prompt_hash))
        
    # Extract the 'outcome' field from each run's model
    outcome_counts = {}
    for model, _ in results:
        # Assumes the Pydantic model has an 'outcome' attribute
        outcome = getattr(model, "outcome", None)
        if outcome is None:
            # Fallback if outcome is not present, use the string representation
            outcome = str(model.model_dump())
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        
    # Find the majority outcome
    majority_outcome = max(outcome_counts.keys(), key=lambda k: outcome_counts[k])
    agreement_rate = outcome_counts[majority_outcome] / num_samples
    
    # Return the first model that had the majority outcome, along with the prompt_hash
    majority_result, prompt_hash = next(r for r in results if getattr(r[0], "outcome", str(r[0].model_dump())) == majority_outcome)
    
    # Override the raw LLM confidence_score with our calibrated one?
    # No, we just return it and let the caller handle it.
    
    confidence_source = f"semantic_consistency_n{num_samples}"
    
    return majority_result, prompt_hash, agreement_rate, confidence_source
