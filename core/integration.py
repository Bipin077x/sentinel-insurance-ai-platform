from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.models import Policy, Decision
from datetime import datetime

class PolicyAdminAdapter(ABC):
    """
    Abstract interface for communicating with a core Policy Administration System (PAS).
    
    REAL IMPLEMENTATION REQUIREMENTS:
    - Auth: Needs to handle OAuth2 client credentials flow or mutual TLS.
    - Rate Limits: Must implement exponential backoff and adhere to PAS API limits (e.g., 100 req/sec).
    - Data Mapping: Must robustly map legacy PAS JSON schemas (which might use different field names or data types) into our internal `Policy` Pydantic model.
    """
    
    @abstractmethod
    def fetch_policy(self, policy_number: str) -> Policy:
        pass
        
    @abstractmethod
    def push_decision(self, decision: Decision) -> bool:
        pass


class CoreBankingAdapter(ABC):
    """
    Abstract interface for communicating with Core Banking or Payment Gateway.
    
    REAL IMPLEMENTATION REQUIREMENTS:
    - Auth: PCI-DSS compliant secure token exchange.
    - Data Mapping: Handling varying date formats, currency conversions, and reconciling batch vs real-time transactions.
    """
    
    @abstractmethod
    def fetch_transactions(self, date_range: tuple) -> List[Dict[str, Any]]:
        pass


class MockPolicyAdminAdapter(PolicyAdminAdapter):
    """
    POC Implementation backed by our synthetic SQLite database.
    """
    def fetch_policy(self, policy_number: str) -> Policy:
        from core.database import SessionLocal, PolicyRecord
        import json
        
        with SessionLocal() as db:
            record = db.query(PolicyRecord).filter(PolicyRecord.policy_number == policy_number).first()
            if not record:
                raise ValueError(f"Policy {policy_number} not found in Mock PAS.")
                
            return Policy(
                policy_number=record.policy_number,
                product_type=record.product_type,
                coverage_limits=json.loads(record.coverage_limits),
                exclusions=json.loads(record.exclusions),
                premium=record.premium,
                effective_date=record.effective_date,
                expiry_date=record.expiry_date,
                holder_id=record.holder_id
            )

    def push_decision(self, decision: Decision) -> bool:
        # In a real system, this updates the PAS state (e.g., marking a claim as Paid).
        # For POC, we just print or return True since ReasoningLog already persists it locally.
        print(f"[Mock PAS] Successfully pushed decision {decision.id} ({decision.outcome}) to Policy Admin System.")
        return True


class MockCoreBankingAdapter(CoreBankingAdapter):
    """
    POC Implementation returning synthetic transactions.
    """
    def fetch_transactions(self, date_range: tuple) -> List[Dict[str, Any]]:
        # Returns mock transactional data
        return [
            {"txn_id": "txn_123", "amount": 150.0, "currency": "USD", "date": datetime.utcnow().isoformat(), "status": "CLEARED"},
            {"txn_id": "txn_124", "amount": -5000.0, "currency": "USD", "date": datetime.utcnow().isoformat(), "status": "PENDING"}
        ]
