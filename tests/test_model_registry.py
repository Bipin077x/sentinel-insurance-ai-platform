import os
import yaml
from core.database import init_db, SessionLocal, ModelChangeLogRecord
from core.model_registry import check_and_log_model_version, get_active_model, CONFIG_PATH

def test_model_registry_logging():
    init_db()
    
    # 1. Setup config
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump({"model_id": "test-model-1.0"}, f)
        
    # 2. Check and log (First time, should log)
    check_and_log_model_version()
    
    db = SessionLocal()
    logs = db.query(ModelChangeLogRecord).order_by(ModelChangeLogRecord.timestamp.desc()).all()
    assert len(logs) >= 1
    assert logs[0].model_id_used == "test-model-1.0"
    
    # 3. Check again (No change, should NOT log a new record)
    initial_count = db.query(ModelChangeLogRecord).count()
    check_and_log_model_version()
    assert db.query(ModelChangeLogRecord).count() == initial_count
    
    # 4. Update config (Change, should log)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump({"model_id": "test-model-2.0"}, f)
        
    check_and_log_model_version()
    
    new_count = db.query(ModelChangeLogRecord).count()
    assert new_count == initial_count + 1
    
    latest_log = db.query(ModelChangeLogRecord).order_by(ModelChangeLogRecord.timestamp.desc()).first()
    assert latest_log.model_id_used == "test-model-2.0"
    
    # Restore original so we don't break pipeline tests
    with open(CONFIG_PATH, "w") as f:
        yaml.dump({"model_id": "mock-llm-1.0-0613"}, f)
