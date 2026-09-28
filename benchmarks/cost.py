import json

PRICING_REFERENCE = {
    "note": "Approximate only. Verify against actual provider pricing before use.",
    "source": "OpenAI API pricing page (accessed 2026-09-23) — model prices vary; update this table for your actual model.",
    "input_per_1k_tokens": 0.005,   # GPT-4o as reference
    "output_per_1k_tokens": 0.015,
}

def estimate_tokens(text: str) -> int:
    """Estimates token counts using len(prompt.split()) * 1.3"""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)

def calculate_cost(input_text: str = "", output_text: str = "", num_samples: int = 1) -> dict:
    in_tokens = estimate_tokens(input_text)
    out_tokens = estimate_tokens(output_text)
    
    # Calibration multiplies the input/output tokens by the number of samples
    total_in_tokens = in_tokens * num_samples
    total_out_tokens = out_tokens * num_samples
    
    in_cost = (total_in_tokens / 1000) * PRICING_REFERENCE["input_per_1k_tokens"]
    out_cost = (total_out_tokens / 1000) * PRICING_REFERENCE["output_per_1k_tokens"]
    total_cost = in_cost + out_cost
    
    return {
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_input_tokens": total_in_tokens,
        "total_output_tokens": total_out_tokens,
        "num_samples": num_samples,
        "estimated_cost": total_cost,
        "projected_cost_1000": total_cost * 1000
    }
