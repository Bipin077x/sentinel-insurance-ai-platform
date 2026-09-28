import os
import json
import hashlib
from datetime import datetime, timezone
import uuid
from core.database import SessionLocal, ReportLogRecord, Base, engine
from core.models import ReportLog

# Ensure table exists
Base.metadata.create_all(bind=engine)

def save_and_log_report(report_content: str, report_type: str, filters: dict, filename: str) -> str:
    """
    Saves a generated report to disk and logs its hash to the database
    to ensure non-repudiation of the report generation event itself.
    """
    os.makedirs("reports", exist_ok=True)
    file_path = os.path.join("reports", filename)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    content_hash = hashlib.sha256(report_content.encode("utf-8")).hexdigest()
    
    with SessionLocal() as db:
        log_entry = ReportLogRecord(
            id=str(uuid.uuid4()),
            report_type=report_type,
            pipeline_filters=json.dumps(filters),
            timestamp=datetime.now(timezone.utc),
            content_hash=content_hash,
            file_path=file_path
        )
        db.add(log_entry)
        db.commit()
        
    return file_path
