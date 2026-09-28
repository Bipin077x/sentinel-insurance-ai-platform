import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from data.load_real_claims import load_real_claims
from core.redaction import redact_snapshot

def main():
    claims_data = load_real_claims("data/insurance_claims.csv")
    claim = claims_data[0][0]
    
    # Test redaction
    snapshot = claim.model_dump(mode='json')
    print("Original:")
    print(snapshot)
    
    redacted = redact_snapshot(snapshot)
    print("\nRedacted:")
    print(redacted)

if __name__ == "__main__":
    main()
