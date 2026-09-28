import json
from data.load_real_claims import load_real_claims
from core.redaction import redact_text

def run_redaction_check():
    claims = load_real_claims()
    print(f"Loaded {len(claims)} claims for redaction check.")
    
    # Take a sample to run through the redaction layer
    sample = claims[:5]
    
    print("\n--- Redaction Sanity Check ---")
    for i, (claim, is_fraud, raw) in enumerate(sample):
        # We'll just serialize the raw row to JSON string and redact it
        text_to_redact = json.dumps(raw)
        redacted = redact_text(text_to_redact)
        
        print(f"\nClaim {i+1}:")
        print(f"Original len: {len(text_to_redact)}")
        print(f"Redacted len: {len(redacted)}")
        
        # Check if anything was redacted (our fake PII rules might trigger on random text)
        if redacted != text_to_redact:
            print(f"Redaction modified the text (Expected since regex might catch SSN/Phone shapes).")
        else:
            print(f"No redaction occurred.")

if __name__ == "__main__":
    run_redaction_check()
