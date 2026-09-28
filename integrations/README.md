# Integration Adapters

This package contains the reference implementation of abstract boundaries to core external systems (Policy Admin, Claims System, Payments, and Document Ingestion).

**Pre-Production Requirement Note:**
These adapters currently use `httpx` to communicate with a local mock FastAPI server (`mock_server.py`). 
To take this AI platform to production, these concrete HTTP adapters must be replaced with the actual client libraries or API calls required by the company's real core systems.

## Running the Mock Server

To test integrations, run the mock server in a separate terminal:
```bash
venv/Scripts/uvicorn integrations.mock_server:app --port 8765
```

You can then run pipelines with the `--use-adapters` flag:
```bash
venv/Scripts/python.exe -m claims.run_claims --use-adapters
```

## Failure Injection
The mock server supports failure injection for robustness testing. You can test the adapters' exponential backoff retry logic by sending requests with query params like `?inject_failure=500`.
