import json
from sqlalchemy import create_engine, Column, String, Float, DateTime, Enum, Text, ForeignKey, inspect
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from core.models import FunctionType, DecisionStatus
from datetime import datetime

Base = declarative_base()

class ComplianceHistoryRecord(Base):
    __tablename__ = 'compliance_history'

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    ruleset_hash = Column(String, nullable=False)
    version_label = Column(String, nullable=False)
    loaded_by = Column(String, nullable=False)

class ModelChangeLogRecord(Base):
    __tablename__ = "model_changelog"
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime)
    model_id_used = Column(String)
    changed_by = Column(String)
    reason = Column(String)

class DecisionRecord(Base):
    __tablename__ = 'decisions'

    id = Column(String, primary_key=True)
    function_type = Column(Enum(FunctionType), nullable=False)
    subject_id = Column(String, nullable=False)
    outcome = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    confidence_source = Column(String, nullable=False, default="unknown")
    rules_fired = Column(Text, nullable=False) # JSON encoded list
    reasoning_text = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(DecisionStatus), nullable=False)
    compliance_ruleset_hash = Column(String, nullable=False, default="unknown")
    prompt_hash = Column(String, nullable=False, default="none")
    record_hash = Column(String, nullable=False, unique=True)
    prev_record_hash = Column(String, nullable=True) # Genesis block has no prev
    
    audit_trail = relationship("AuditTrailRecord", back_populates="decision", uselist=False)


class AuditTrailRecord(Base):
    __tablename__ = 'audit_trails'

    decision_id = Column(String, ForeignKey('decisions.id'), primary_key=True)
    inputs_hash = Column(String, nullable=False)
    inputs_snapshot = Column(Text, nullable=False) # JSON encoded dict
    rule_results = Column(Text, nullable=False) # JSON encoded dict
    model_prompt_version = Column(String, nullable=False)
    compliance_ruleset_hash = Column(String, nullable=False, default="unknown")
    prompt_hash = Column(String, nullable=False, default="none")
    reviewer_id = Column(String, nullable=True)
    override_reason = Column(String, nullable=True)
    record_hash = Column(String, nullable=False, unique=True)
    prev_record_hash = Column(String, nullable=True)
    
    decision = relationship("DecisionRecord", back_populates="audit_trail")

class RawDocumentRecord(Base):
    __tablename__ = 'raw_documents'
    
    id = Column(String, primary_key=True)
    decision_id = Column(String, nullable=False) # Not enforcing FK to allow easy isolated deletion
    raw_content = Column(Text, nullable=False)
    retention_expiry = Column(DateTime, nullable=False)

class ReportLogRecord(Base):
    __tablename__ = 'report_logs'
    
    id = Column(String, primary_key=True)
    report_type = Column(String, nullable=False)
    pipeline_filters = Column(Text, nullable=False) # JSON encoded dict
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    content_hash = Column(String, nullable=False)
    file_path = Column(String, nullable=False)

class ReviewRecord(Base):
    __tablename__ = 'review_records'
    id = Column(String, primary_key=True)
    decision_id = Column(String, nullable=False)
    reviewer_id = Column(String, nullable=False)
    action = Column(String, nullable=False)         # "approve" | "deny" | "modify"
    original_outcome = Column(String, nullable=False)
    final_outcome = Column(String, nullable=False)
    justification = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    record_hash = Column(String, nullable=False, unique=True)


class DeletionLogRecord(Base):
    __tablename__ = 'deletion_logs'
    
    id = Column(String, primary_key=True)
    decision_id = Column(String, nullable=False)
    policy_version_hash = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    record_hash = Column(String, nullable=False, unique=True)
    prev_record_hash = Column(String, nullable=True)

# --- Append-Only Enforcement Triggers ---
from sqlalchemy import text


class PolicyRecord(Base):
    __tablename__ = 'policies'

    policy_number = Column(String, primary_key=True)
    product_type = Column(String, nullable=False)
    coverage_limits = Column(Text, nullable=False) # JSON encoded dict
    exclusions = Column(Text, nullable=False) # JSON encoded list
    premium = Column(Float, nullable=False)
    effective_date = Column(DateTime, nullable=False)
    expiry_date = Column(DateTime, nullable=False)
    holder_id = Column(String, nullable=False)

class ClaimRecord(Base):
    __tablename__ = 'claims'

    id = Column(String, primary_key=True)
    policy_id = Column(String, ForeignKey('policies.policy_number'), nullable=False)
    date_filed = Column(DateTime, nullable=False)
    claim_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    cause = Column(String, nullable=False)
    evidence_list = Column(Text, nullable=False) # JSON encoded list

# SQLite database for POC
DATABASE_URL = "sqlite:///./insurance_platform.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Apply triggers unconditionally
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_decisions_update BEFORE UPDATE ON decisions
            BEGIN SELECT RAISE(ABORT, 'UPDATE strictly forbidden on append-only table decisions'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_decisions_delete BEFORE DELETE ON decisions
            BEGIN SELECT RAISE(ABORT, 'DELETE strictly forbidden on append-only table decisions'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_audit_trails_update BEFORE UPDATE ON audit_trails
            BEGIN SELECT RAISE(ABORT, 'UPDATE strictly forbidden on append-only table audit_trails'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_audit_trails_delete BEFORE DELETE ON audit_trails
            BEGIN SELECT RAISE(ABORT, 'DELETE strictly forbidden on append-only table audit_trails'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_review_records_update BEFORE UPDATE ON review_records
            BEGIN SELECT RAISE(ABORT, 'UPDATE strictly forbidden on append-only table review_records'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_review_records_delete BEFORE DELETE ON review_records
            BEGIN SELECT RAISE(ABORT, 'DELETE strictly forbidden on append-only table review_records'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_deletion_logs_update BEFORE UPDATE ON deletion_logs
            BEGIN SELECT RAISE(ABORT, 'UPDATE strictly forbidden on append-only table deletion_logs'); END;
        '''))
        conn.execute(text('''
            CREATE TRIGGER IF NOT EXISTS block_deletion_logs_delete BEFORE DELETE ON deletion_logs
            BEGIN SELECT RAISE(ABORT, 'DELETE strictly forbidden on append-only table deletion_logs'); END;
        '''))
        conn.commit()
