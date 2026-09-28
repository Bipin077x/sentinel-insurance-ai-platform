import json
import hashlib
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "retention.json")

def load_retention_policy(config_path=DEFAULT_CONFIG_PATH):
    if not os.path.exists(config_path):
        # Default fallback config if file doesn't exist
        policy = {
            "raw_documents_pii_days": 30
        }
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(policy, f, indent=2)
            
    with open(config_path, "r") as f:
        config_data = f.read()
        
    policy = json.loads(config_data)
    # Compute SHA-256 of the exact configuration string
    policy_hash = hashlib.sha256(config_data.encode('utf-8')).hexdigest()
    
    return policy, policy_hash
