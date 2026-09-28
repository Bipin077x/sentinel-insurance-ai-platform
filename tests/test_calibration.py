import pytest
from pydantic import BaseModel
from core.calibration import compute_semantic_entropy

class MockOutput(BaseModel):
    outcome: str
    confidence: float
    reasoning_text: str

def test_semantic_entropy_consistent():
    """
    Test a synthetic case where single-shot LLM output is perfectly consistent.
    Should yield 1.0 computed confidence.
    """
    def consistent_llm_caller():
        # Always returns "approve"
        return MockOutput(outcome="approve", confidence=0.9, reasoning_text="Clear cut case."), "hash1"

    result, prompt_hash, agreement_rate, source = compute_semantic_entropy(consistent_llm_caller, num_samples=5)
    
    assert result.outcome == "approve"
    assert prompt_hash == "hash1"
    assert agreement_rate == 1.0
    assert source == "semantic_consistency_n5"

def test_semantic_entropy_ambiguous():
    """
    Test a synthetic case where the LLM output is genuinely ambiguous.
    Should yield a lower computed confidence.
    """
    import random
    
    def ambiguous_llm_caller():
        # Mix of "approve" and "review"
        val = random.random()
        if val < 0.6:
            return MockOutput(outcome="review", confidence=0.8, reasoning_text="Looks risky."), "hash2"
        else:
            return MockOutput(outcome="approve", confidence=0.7, reasoning_text="Looks okay."), "hash2"
            
    # Run a test where we force the random seed to guarantee a mix
    random.seed(42) # For reproducibility: random() will give deterministic sequence
    
    result, prompt_hash, agreement_rate, source = compute_semantic_entropy(ambiguous_llm_caller, num_samples=5)
    
    # Let's check what the 5 samples give with seed 42
    # 0.639 (approve), 0.025 (review), 0.275 (review), 0.223 (review), 0.736 (approve)
    # So 3 reviews, 2 approves -> majority is 'review'
    
    assert result.outcome == "review"
    assert prompt_hash == "hash2"
    assert agreement_rate == 0.6
    assert source == "semantic_consistency_n5"

