from fastapi import FastAPI, Request, Response, Header, HTTPException
import xml.etree.ElementTree as ET
import uuid
import time
from typing import Optional, Dict

app = FastAPI()

# In-memory stores
idempotency_cache: Dict[str, str] = {}
async_jobs: Dict[str, Dict] = {}
backend_apply_count: int = 0

def build_xml_response(correlation_id: str, body_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Envelope>
    <Header>
        <CorrelationId>{correlation_id}</CorrelationId>
    </Header>
    <Body>
        {body_xml}
    </Body>
</Envelope>"""

@app.post("/policy/update")
async def update_policy(
    request: Request,
    correlation_id: Optional[str] = Header(None, alias="CorrelationId"),
    idempotency_key: Optional[str] = Header(None, alias="IdempotencyKey")
):
    global backend_apply_count
    
    if not correlation_id:
        raise HTTPException(status_code=400, detail="Missing CorrelationId header")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Missing IdempotencyKey header")
        
    body = await request.body()
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise HTTPException(status_code=400, detail="Invalid XML payload")
        
    # Check idempotency
    if idempotency_key in idempotency_cache:
        job_id = idempotency_cache[idempotency_key]
        return Response(
            content=build_xml_response(correlation_id, f"<JobId>{job_id}</JobId><Status>Retrieved</Status><ApplyCount>{backend_apply_count}</ApplyCount>"),
            media_type="application/xml",
            status_code=202
        )
        
    # Simulate a network failure on the first try if requested (to test adapter retry behavior)
    decision_el = root.find(".//Decision")
    outcome = decision_el.text if decision_el is not None else "accept"
    
    if outcome == "force_503_once" and idempotency_key not in idempotency_cache:
        # We use a hack: store it in cache but return 503, so the next try with SAME key will proceed
        if not hasattr(app, "failed_once"):
            app.failed_once = set()
            
        if idempotency_key not in app.failed_once:
            app.failed_once.add(idempotency_key)
            return Response(status_code=503, content="Service Unavailable Simulated")

    # Increment actual backend apply count
    backend_apply_count += 1
    
    job_id = str(uuid.uuid4())
    idempotency_cache[idempotency_key] = job_id
    
    # Start Job
    if outcome == "timeout_sim":
        async_jobs[job_id] = {"status": "PENDING", "created_at": time.time(), "type": "never_resolves"}
    elif outcome == "partial_fail_sim":
        async_jobs[job_id] = {"status": "PENDING", "created_at": time.time(), "type": "partial_failure"}
    else:
        async_jobs[job_id] = {"status": "PENDING", "created_at": time.time(), "type": "success"}

    return Response(
        content=build_xml_response(correlation_id, f"<JobId>{job_id}</JobId><Status>Accepted</Status><ApplyCount>{backend_apply_count}</ApplyCount>"),
        media_type="application/xml",
        status_code=202
    )

@app.get("/status/{job_id}")
async def get_status(
    job_id: str,
    correlation_id: Optional[str] = Header(None, alias="CorrelationId")
):
    if not correlation_id:
        raise HTTPException(status_code=400, detail="Missing CorrelationId header")
        
    if job_id not in async_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job = async_jobs[job_id]
    
    # Simulate processing time
    if time.time() - job["created_at"] < 2.0:
        return Response(
            content=build_xml_response(correlation_id, f"<JobId>{job_id}</JobId><Status>PENDING</Status>"),
            media_type="application/xml",
            status_code=200
        )
        
    # Resolve job based on type
    if job["type"] == "never_resolves":
        return Response(
            content=build_xml_response(correlation_id, f"<JobId>{job_id}</JobId><Status>PENDING</Status>"),
            media_type="application/xml",
            status_code=200
        )
    elif job["type"] == "partial_failure":
        body = f"""<JobId>{job_id}</JobId>
<Status>PARTIAL_SUCCESS</Status>
<Details>
    <System name="PolicyAdmin">SUCCESS</System>
    <System name="Billing">FAILED - Timeout</System>
</Details>"""
        return Response(content=build_xml_response(correlation_id, body), media_type="application/xml", status_code=200)
    else:
        body = f"<JobId>{job_id}</JobId><Status>CONFIRMED</Status>"
        return Response(content=build_xml_response(correlation_id, body), media_type="application/xml", status_code=200)

@app.post("/mock/reset")
async def reset_mock():
    global backend_apply_count
    idempotency_cache.clear()
    async_jobs.clear()
    backend_apply_count = 0
    if hasattr(app, "failed_once"):
        app.failed_once.clear()
    return {"status": "reset"}

@app.get("/mock/state")
async def get_state():
    return {"backend_apply_count": backend_apply_count}
