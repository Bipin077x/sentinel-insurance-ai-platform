import yaml
import uuid
import os
from datetime import datetime, timezone
from core.database import SessionLocal, ModelChangeLogRecord

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "model_config.yaml")

def get_active_model() -> str:
    """Reads the pinned model ID from the configuration file."""
    if not os.path.exists(CONFIG_PATH):
        # Default fallback if config is missing during tests
        return "mock-llm-1.0"
        
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config.get("model_id", "mock-llm-1.0")

def check_and_log_model_version():
    """
    Checks if the active pinned model differs from the last one recorded in the change log.
    If so, logs a new change record. This acts as an immutable ledger of model versioning.
    """
    active_model = get_active_model()
    
    db = SessionLocal()
    try:
        # Get the latest logged model version
        latest_log = db.query(ModelChangeLogRecord).order_by(ModelChangeLogRecord.timestamp.desc()).first()
        
        if not latest_log or latest_log.model_id_used != active_model:
            # We have a new model version (or first run)! Log it.
            new_log = ModelChangeLogRecord(
                id=f"mlog_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now(timezone.utc),
                model_id_used=active_model,
                changed_by="system_startup",
                reason="Configuration update detected or initial run"
            )
            db.add(new_log)
            db.commit()
            print(f"[*] Model Registry: Logged new pinned model version -> {active_model}")
    finally:
        db.close()
