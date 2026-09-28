import jcs
import hashlib
from typing import Dict, Any

def compute_canonical_hash(data: Dict[str, Any]) -> str:
    """
    Computes a cryptographic hash using RFC 8785 JSON Canonicalization Scheme (JCS).
    This ensures that identical logical data always produces the exact same hash,
    regardless of key ordering or insignificant whitespace.
    """
    # jcs.canonicalize requires the input to be a dict (or list, but usually dict for records)
    # It returns bytes representing the canonical JSON string.
    canonical_bytes = jcs.canonicalize(data)
    
    # Compute SHA-256 hash of the canonical bytes
    return hashlib.sha256(canonical_bytes).hexdigest()
