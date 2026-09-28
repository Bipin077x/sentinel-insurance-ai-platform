"""
integrations/mock_adapters.py — Concrete HTTP implementations of base interfaces.

Uses httpx with explicit retry logic (exponential backoff).
Raises IntegrationError if retries are exhausted.
Logs integration boundaries to a local file, not the main DB (avoids WORM issues).
"""

import os
import json
import time
from datetime import datetime
import httpx
from pydantic import BaseModel

from core.models import Claim, Decision
from integrations.base import (
    ClaimsSystemAdapter,
    PaymentAdapter,
    PolicyAdminAdapter,
    DocumentIngestAdapter,
    PaymentResult,
    IntegrationError
)
from integrations.config import MOCK_SERVER_URL


def _log_integration(action: str, payload: dict, success: bool, error: str = ""):
    os.makedirs("scratch", exist_ok=True)
    with open("scratch/integration_log.jsonl", "a", encoding="utf-8") as f:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "success": success,
            "payload": payload,
            "error": error
        }
        f.write(json.dumps(log_entry) + "\n")


def _http_post_with_retry(url: str, json_data: dict, max_retries: int = 3) -> dict:
    """Helper with exponential backoff on 5xx or timeouts."""
    attempt = 0
    while attempt < max_retries:
        try:
            # Short timeout to fail fast for test purposes
            resp = httpx.post(url, json=json_data, timeout=2.0)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError("5xx Error", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            attempt += 1
            if attempt >= max_retries:
                raise IntegrationError(f"Exhausted {max_retries} retries for POST {url}. Last error: {str(e)}")
            time.sleep(1.0 * (2 ** (attempt - 1)))  # Backoff: 1s, 2s, ...


def _http_get_with_retry(url: str, max_retries: int = 3) -> dict:
    attempt = 0
    while attempt < max_retries:
        try:
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError("5xx Error", request=resp.request, response=resp)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            # Don't retry 404s
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                return None
            attempt += 1
            if attempt >= max_retries:
                raise IntegrationError(f"Exhausted {max_retries} retries for GET {url}. Last error: {str(e)}")
            time.sleep(1.0 * (2 ** (attempt - 1)))


class HttpClaimsAdapter(ClaimsSystemAdapter):
    def fetch_claim(self, claim_id: str) -> Claim | None:
        url = f"{MOCK_SERVER_URL}/claims/{claim_id}"
        data = _http_get_with_retry(url)
        if not data:
            return None
        return Claim(**data)

    def push_claim_decision(self, decision: Decision) -> bool:
        url = f"{MOCK_SERVER_URL}/decisions"
        payload = decision.model_dump(mode="json")
        try:
            _http_post_with_retry(url, payload)
            _log_integration("push_claim_decision", payload, True)
            return True
        except IntegrationError as e:
            _log_integration("push_claim_decision", payload, False, str(e))
            raise


class HttpPaymentAdapter(PaymentAdapter):
    def initiate_payout(self, decision_id: str, amount: float, payee: str) -> PaymentResult:
        url = f"{MOCK_SERVER_URL}/payments"
        payload = {
            "decision_id": decision_id,
            "amount": amount,
            "payee": payee
        }
        try:
            data = _http_post_with_retry(url, payload)
            _log_integration("initiate_payout", payload, True)
            return PaymentResult(
                payment_id=data["payment_id"],
                status=data["status"],
                amount=data["amount"],
                payee=data["payee"],
                timestamp=datetime.now()
            )
        except IntegrationError as e:
            _log_integration("initiate_payout", payload, False, str(e))
            raise


class HttpPolicyAdminAdapter(PolicyAdminAdapter):
    def fetch_policy(self, policy_number: str) -> dict | None:
        url = f"{MOCK_SERVER_URL}/policy/{policy_number}"
        return _http_get_with_retry(url)

    def push_decision(self, decision: Decision) -> bool:
        url = f"{MOCK_SERVER_URL}/decisions"
        payload = decision.model_dump(mode="json")
        try:
            _http_post_with_retry(url, payload)
            _log_integration("push_policy_decision", payload, True)
            return True
        except IntegrationError as e:
            _log_integration("push_policy_decision", payload, False, str(e))
            raise


class HttpDocumentIngestAdapter(DocumentIngestAdapter):
    def fetch_pending_documents(self) -> list[dict]:
        url = f"{MOCK_SERVER_URL}/documents/pending"
        data = _http_get_with_retry(url)
        return data if data else []
