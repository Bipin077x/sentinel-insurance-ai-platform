import json
import os
import hashlib

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
MANIFEST_PATH = os.path.join(PROMPTS_DIR, "manifest.json")

def load_prompt(name: str, version: str) -> tuple[str, str]:
    """
    Loads a versioned prompt template from disk, verifies its cryptographic hash 
    against the central manifest, and returns the (template_text, prompt_hash).
    """
    manifest = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r") as f:
            manifest = json.load(f)
            
    key = f"{name}_{version}"
    expected_hash = manifest.get(key)
    
    if not expected_hash:
        raise ValueError(f"Prompt {key} not found in prompt registry manifest.")
        
    prompt_path = os.path.join(PROMPTS_DIR, f"{key}.txt")
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Prompt file {prompt_path} is missing.")
        
    with open(prompt_path, "rb") as f:
        file_bytes = f.read()
        
    actual_hash = hashlib.sha256(file_bytes).hexdigest()
    
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"EVIDENTIARY INTEGRITY FAILURE: Prompt {key} hash mismatch! "
            f"Expected {expected_hash}, got {actual_hash}. "
            "Someone has altered an immutable prompt template."
        )
        
    return file_bytes.decode("utf-8"), actual_hash
