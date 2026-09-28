"""
integrations/mock_server.py — FastAPI mock server for Phase 6.

Simulates the Policy Admin, Claims, and Payment systems.
Maintains state in memory to allow integration tests to verify POSTs.

Run via: venv/Scripts/uvicorn integrations.mock_server:app --port 8765 --reload
"""

import uuid
import asyncio
import json
import os
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any

app = FastAPI(title="Mock Insurance Core Systems")

# In-memory store to verify what the AI pushed
received_data: Dict[str, List[Any]] = {
    "decisions": [],
    "payments": []
}

# Preload synthetic claims for fetching
SYNTHETIC_CLAIMS = {}
try:
    with open("synthetic_claims.json", "r") as f:
        data = json.load(f)
        if isinstance(data, list):
            for c in data:
                # The dict has "claim_id"
                SYNTHETIC_CLAIMS[c.get("claim_id", c.get("id"))] = c
except FileNotFoundError:
    print("Warning: synthetic_claims.json not found. GET /claims will 404.")


@app.middleware("http")
async def failure_injector(request: Request, call_next):
    """
    Middleware to inject failures if requested via query param.
    e.g. ?inject_failure=timeout or ?inject_failure=500
    """
    failure_type = request.query_params.get("inject_failure")
    if failure_type == "timeout":
        await asyncio.sleep(5)  # Simulate slow response
        return Response("Gateway Timeout", status_code=504)
    elif failure_type == "500":
        return Response("Internal Server Error (Simulated)", status_code=500)
    
    response = await call_next(request)
    return response


@app.get("/claims/{claim_id}")
async def get_claim(claim_id: str):
    if claim_id not in SYNTHETIC_CLAIMS:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    raw = SYNTHETIC_CLAIMS[claim_id]
    return {
        "id": raw.get("claim_id", claim_id),
        "policy_id": raw.get("policy_id", "UNKNOWN"),
        "date_filed": raw.get("date_filed", "2026-01-01T00:00:00Z"),
        "incident_date": "2026-01-01T00:00:00Z",
        "claim_type": "mock_type",
        "amount": 1000.0,
        "cause": "mock cause",
        "evidence_list": raw.get("evidence", [])
    }


@app.post("/decisions")
async def post_decision(request: Request):
    data = await request.json()
    received_data["decisions"].append(data)
    return {"status": "accepted", "message": "Decision logged in core system"}


class PaymentRequest(BaseModel):
    decision_id: str
    amount: float
    payee: str

@app.post("/payments")
async def post_payment(req: PaymentRequest):
    payment_id = str(uuid.uuid4())
    record = {
        "payment_id": payment_id,
        "decision_id": req.decision_id,
        "amount": req.amount,
        "payee": req.payee,
        "status": "initiated",
    }
    received_data["payments"].append(record)
    return record


@app.get("/documents/pending")
async def get_pending_documents():
    return [
        {"doc_id": "doc_1001", "type": "pdf", "path": "ingestion/test_documents/native_claim.pdf"},
        {"doc_id": "doc_1002", "type": "image", "path": "ingestion/test_documents/scanned_claim.png"}
    ]


@app.get("/mock/received")
async def get_received_data():
    """Endpoint for tests to assert data was pushed correctly."""
    return received_data

@app.post("/mock/reset")
async def reset_mock():
    received_data["decisions"].clear()
    received_data["payments"].clear()
    return {"status": "reset"}

