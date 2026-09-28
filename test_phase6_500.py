import asyncio
from datetime import datetime
from integrations.mock_adapters import HttpClaimsAdapter, IntegrationError
from core.models import Decision, FunctionType, DecisionStatus
import integrations.mock_adapters

def test_500():
    # We can't just change the URL because it appends /decisions
    # If MOCK_SERVER_URL = "http://localhost:8765", url becomes "http://localhost:8765/decisions"
    # To pass ?inject_failure=500, we should monkey patch the URL builder or just change MOCK_SERVER_URL
    integrations.mock_adapters.MOCK_SERVER_URL = "http://127.0.0.1:8765/decisions?inject_failure=500&"
    
    # Wait, HttpClaimsAdapter does: url = f"{MOCK_SERVER_URL}/decisions"
    # So if we set MOCK_SERVER_URL = "http://127.0.0.1:8765", url becomes "http://127.0.0.1:8765/decisions"
    
    # Let's just monkeypatch HttpClaimsAdapter's push_claim_decision to add the query param
    original_push = HttpClaimsAdapter.push_claim_decision
    
    adapter = HttpClaimsAdapter()
    
    # Alternatively, just write a new function to post to http://127.0.0.1:8765/decisions?inject_failure=500
    from integrations.mock_adapters import _http_post_with_retry
    
    try:
        _http_post_with_retry("http://127.0.0.1:8765/decisions?inject_failure=500", {"test": "data"}, max_retries=3)
        print("FAIL: Did not raise IntegrationError")
    except IntegrationError as e:
        print("SUCCESS: Raised IntegrationError on 500")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_500()
