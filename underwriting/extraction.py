import json
import re
from core.models import Document, Application
from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt
from core.validators import validate_application

class ExtractionValidationError(Exception):
    def __init__(self, errors: list[str], prompt_hash: str):
        self.errors = errors
        self.prompt_hash = prompt_hash
        super().__init__("Extraction validation failed")

def extract_application_info(document: Document) -> tuple[Application, str]:
    """
    Extracts structured application details from raw text via LLM.
    Returns the application and the prompt_hash used.
    """
    template, prompt_hash = load_prompt("underwriting_extraction", "v1")
    prompt = template.replace("{{document_text}}", document.raw_text)
    
    def mock_llm_extraction(p, schema):
        text = document.raw_text.lower()
        
        # Simple extraction heuristics to mock LLM behavior
        age_match = re.search(r'i am (\d+) years old', text)
        age = int(age_match.group(1)) if age_match else 30
        
        cost_match = re.search(r'\$(-?\d+(?:\.\d{2})?)', text)
        cost = float(cost_match.group(1)) if cost_match else 1000.0
        
        dur_match = re.search(r'for (\d+) days', text)
        duration = int(dur_match.group(1)) if dur_match else 7
        
        pre_existing = "no pre-existing" not in text and "pre-existing" in text and "false" not in text
        
        dest = "Unknown"
        if "france" in text: dest = "France"
        elif "italy" in text: dest = "Italy"
        elif "north korea" in text: dest = "North Korea"
        elif "switzerland" in text: dest = "Switzerland"
        elif "mars" in text: dest = "Mars"
        elif "japan" in text: dest = "Japan"
        
        activities = []
        if "sightseeing" in text: activities.append("sightseeing")
        if "museums" in text: activities.append("museums")
        if "walking" in text: activities.append("walking")
        if "guided tour" in text: activities.append("guided tour")
        if "skiing" in text: activities.append("skiing")
        if "hiking" in text: activities.append("hiking")
        if "base jumping" in text: activities.append("base jumping")
        if "heli-skiing" in text: activities.append("heli-skiing")
        if "free solo climbing" in text: activities.append("free solo climbing")
        if "wingsuit flying" in text: activities.append("wingsuit flying")
            
        return json.dumps({
            "id": document.source_metadata["app_id"],
            "age": age,
            "destination": dest,
            "trip_cost": cost,
            "pre_existing_conditions": pre_existing,
            "trip_duration_days": duration,
            "planned_activities": activities
        })

    app_data = call_llm_with_schema(prompt, Application, mock_llm_extraction)
    
    validation_errors = validate_application(app_data)
    if validation_errors:
        raise ExtractionValidationError(validation_errors, prompt_hash)
        
    return app_data, prompt_hash
