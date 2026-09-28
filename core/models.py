from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class FunctionType(str, Enum):
    BROKERAGE = "brokerage"
    UNDERWRITING = "underwriting"
    CLAIMS = "claims"
    AUDIT = "audit"
    EXTRACTION_VALIDATION = "extraction_validation"

class DecisionStatus(str, Enum):
    AUTO_DECIDED = "auto_decided"
    PENDING_REVIEW = "pending_review"
    HUMAN_OVERRIDDEN = "human_overridden"

class Party(BaseModel):
    id: str
    name: str
    contact_info: Dict[str, str]

class Policy(BaseModel):
    policy_number: str
    product_type: str
    coverage_limits: Dict[str, float]
    exclusions: List[str]
    premium: float
    effective_date: datetime
    expiry_date: datetime
    holder_id: str

class Document(BaseModel):
    id: str
    doc_type: str
    raw_text: str
    source_metadata: Dict[str, Any]

class Decision(BaseModel):
    id: str
    function_type: FunctionType
    subject_id: str
    outcome: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_source: str
    rules_fired: List[str]
    reasoning_text: str
    model_version: str
    timestamp: datetime
    status: DecisionStatus
    compliance_ruleset_hash: str
    prompt_hash: Optional[str] = None
    record_hash: Optional[str] = None
    prev_record_hash: Optional[str] = None

class AuditTrailEntry(BaseModel):
    decision_id: str
    inputs_hash: str
    inputs_snapshot: Dict[str, Any]
    rule_results: Dict[str, Any]
    model_prompt_version: str
    compliance_ruleset_hash: str
    prompt_hash: Optional[str] = None
    reviewer_id: Optional[str] = None
    override_reason: Optional[str] = None
    record_hash: Optional[str] = None
    prev_record_hash: Optional[str] = None

class RawDocumentStore(BaseModel):
    id: str
    decision_id: str
    raw_content: str
    retention_expiry: datetime

class Claim(BaseModel):
    id: str
    policy_id: str
    date_filed: datetime
    incident_date: datetime
    claim_type: str
    amount: float
    cause: str
    evidence_list: List[str]

class RuleResult(BaseModel):
    rule_name: str
    passed: bool
    detail: str

class Application(BaseModel):
    id: str
    age: int
    destination: str
    trip_cost: float
    pre_existing_conditions: bool
    trip_duration_days: int
    planned_activities: List[str]

class ClientNeeds(BaseModel):
    client_id: str
    destination: str
    duration_days: int
    coverage_priorities: List[str]
    activities: List[str]
    pre_existing_conditions: bool
    budget_signal: str

class CatalogProduct(BaseModel):
    product_id: str
    name: str
    base_price: float
    features: List[str]
    eligibility_rules: Dict[str, Any]
    exclusion_list: List[str]

class ModelChangeLog(BaseModel):
    id: str
    timestamp: datetime
    model_id_used: str
    changed_by: str
    reason: str

class ReportLog(BaseModel):
    id: str
    report_type: str
    pipeline_filters: Dict[str, Any]
    timestamp: datetime
    content_hash: str
    file_path: str
