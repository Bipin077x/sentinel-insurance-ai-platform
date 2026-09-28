from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReviewRecordModel(BaseModel):
    id: str
    decision_id: str
    reviewer_id: str
    action: str
    original_outcome: str
    final_outcome: str
    justification: str
    timestamp: datetime
    record_hash: str
