"""
integrations/base.py — Abstract interfaces for external integrations.

These are the contracts the AI system uses to interact with the outside world.
Reference implementations (mock_adapters.py) implement these interfaces against
the mock REST server.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from core.models import Claim, Application, Decision


class PaymentResult(BaseModel):
    payment_id: str
    status: str
    amount: float
    payee: str
    timestamp: datetime


class PolicyAdminAdapter(ABC):
    @abstractmethod
    def fetch_policy(self, policy_number: str) -> Optional[dict]:
        """Fetches policy details from the Policy Admin System."""
        pass

    @abstractmethod
    def push_decision(self, decision: Decision) -> bool:
        """Pushes an underwriting or brokerage decision back to Policy Admin."""
        pass


class ClaimsSystemAdapter(ABC):
    @abstractmethod
    def fetch_claim(self, claim_id: str) -> Optional[Claim]:
        """Fetches structured claim data from the core claims system."""
        pass

    @abstractmethod
    def push_claim_decision(self, decision: Decision) -> bool:
        """Pushes a claims adjudication decision back to the core claims system."""
        pass


class PaymentAdapter(ABC):
    @abstractmethod
    def initiate_payout(self, decision_id: str, amount: float, payee: str) -> PaymentResult:
        """Initiates a payment for an approved claim."""
        pass


class DocumentIngestAdapter(ABC):
    @abstractmethod
    def fetch_pending_documents(self) -> List[dict]:
        """Fetches pending raw documents (PDFs, images) waiting for AI processing."""
        pass


class IntegrationError(Exception):
    """Raised when an adapter exhausts retries interacting with the external system."""
    pass
