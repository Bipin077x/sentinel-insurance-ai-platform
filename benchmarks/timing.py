import time
from functools import wraps
from typing import Dict

stage_durations: Dict[str, float] = {}

class stage_timer:
    """Context manager and decorator for timing pipeline stages."""
    def __init__(self, stage_name: str):
        self.stage_name = stage_name
        
    def __enter__(self):
        self.start = time.perf_counter()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start
        if self.stage_name not in stage_durations:
            stage_durations[self.stage_name] = 0.0
        stage_durations[self.stage_name] += duration
        
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper

def reset_timers():
    stage_durations.clear()
