import pytest
from datetime import datetime, timezone
from core.database import init_db, engine, Base
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision, get_decision_trail

@pytest.fixture(autouse=True)
def setup_database():
    # Setup the in-memory or POC test database
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_reasoning_log_roundtrip():
    # Create test data
    now = datetime.now(timezone.utc)
    
    decision = Decision(
        id="dec-001",
        function_type=FunctionType.UNDERWRITING,
        subject_id="pol-123",
        outcome="approved",
        confidence_score=0.92,
        rules_fired=["rule1", "rule2"],
        reasoning_text="The risk is acceptable.",
        model_version="gemini-3.1-pro",
        timestamp=now,
        status=DecisionStatus.AUTO_DECIDED,
        compliance_ruleset_hash="mock_hash",
        confidence_source="self_reported"
    )
    
    audit_trail = AuditTrailEntry(
        decision_id="dec-001",
        inputs_hash="abcd123",
        inputs_snapshot={"test": "data"},
        rule_results={"rule1": True, "rule2": False},
        model_prompt_version="v2",
        compliance_ruleset_hash="mock_hash",
        reviewer_id=None,
        override_reason=None
    )
    
    # Log it
    log_decision(decision, audit_trail)
    
    # Read it back
    trail = get_decision_trail("dec-001")
    assert trail is not None
    
    retrieved_decision = trail["decision"]
    retrieved_audit = trail["audit_trail"]
    
    # Assert fields on Decision
    assert retrieved_decision.id == "dec-001"
    assert retrieved_decision.function_type == FunctionType.UNDERWRITING
    assert retrieved_decision.subject_id == "pol-123"
    assert retrieved_decision.outcome == "approved"
    assert retrieved_decision.confidence_score == 0.92
    assert retrieved_decision.rules_fired == ["rule1", "rule2"]
    assert retrieved_decision.reasoning_text == "The risk is acceptable."
    assert retrieved_decision.model_version == "gemini-3.1-pro"
    assert retrieved_decision.status == DecisionStatus.AUTO_DECIDED
    assert retrieved_decision.confidence_source == "self_reported"
    # Ignoring exact timezone timestamp comparison due to sqlite nuances, just ensure existence
    assert retrieved_decision.timestamp is not None
    
    # Assert fields on AuditTrail
    assert retrieved_audit.decision_id == "dec-001"
    assert retrieved_audit.inputs_hash == "abcd123"
    assert retrieved_audit.inputs_snapshot == {"test": "data"}
    assert retrieved_audit.rule_results == {"rule1": True, "rule2": False}
    assert retrieved_audit.model_prompt_version == "v2"
    assert retrieved_audit.compliance_ruleset_hash == "mock_hash"
    assert retrieved_audit.reviewer_id is None
    assert retrieved_audit.override_reason is None
