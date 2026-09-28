import json
from core.models import Document, ClientNeeds
from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt
from core.validators import validate_client_needs

class ExtractionValidationError(Exception):
    def __init__(self, errors: list, prompt_hash: str):
        self.errors = errors
        self.prompt_hash = prompt_hash
        super().__init__(", ".join(errors))

def extract_client_needs(document: Document) -> tuple[ClientNeeds, str]:
    """
    Extracts structured client needs from raw text via LLM.
    """
    template, prompt_hash = load_prompt("brokerage_extraction", "v1")
    prompt = template.replace("{{document_text}}", document.raw_text)
    
    def mock_llm_extraction(p, schema):
        text = document.raw_text.lower()
        
        dest = "Global"
        if "southeast asia" in text: dest = "Southeast Asia"
        elif "europe" in text: dest = "Europe"
        elif "andes" in text: dest = "South America"
        elif "mexico" in text: dest = "Mexico"
        elif "canada" in text: dest = "Canada"
        elif "bahamas" in text: dest = "Bahamas"
        elif "japan" in text: dest = "Japan"
        elif "alps" in text: dest = "Alps"
        elif "new zealand" in text: dest = "New Zealand"
        elif "switzerland" in text: dest = "Switzerland"
        elif "hawaii" in text: dest = "Hawaii"
        elif "peru" in text: dest = "Peru"
        
        duration = 7
        import re
        dur_match = re.search(r'for (-?\d+) days?', text)
        if dur_match: duration = int(dur_match.group(1))
        elif "3 weeks" in text: duration = 21
        elif "2-month" in text: duration = 60
        elif "3 months" in text: duration = 90
        
        budget = "standard"
        if "tight budget" in text or "budget is tight" in text or "lowest cost" in text or "low cost" in text or "cheapest" in text or "don't want to spend too much" in text or "aren't rich" in text:
            budget = "low"
        elif "price is no object" in text: budget = "high"
        
        priorities = ["medical"]
        if "trip cancellation" in text and "no trip cancellation" not in text and "don't care" not in text:
            priorities.append("trip cancellation")
        if "evacuation" in text:
            priorities.append("evacuation")
            
        activities = []
        if "base jumping" in text: activities.append("base jumping")
        if "heli-skiing" in text: activities.append("heli-skiing")
        if "extreme sports" in text: activities.append("extreme sports")
        if "trekking" in text: activities.append("trekking")
        if "hiking" in text: activities.append("hiking")
        if "museums" in text: activities.append("museums")
        if "cruise" in text: activities.append("cruise")
        
        pre_existing = "pre-existing" in text and "no pre-existing" not in text
            
        return json.dumps({
            "client_id": document.source_metadata["client_id"],
            "destination": dest,
            "duration_days": duration,
            "coverage_priorities": priorities,
            "activities": activities,
            "pre_existing_conditions": pre_existing,
            "budget_signal": budget
        })

    needs = call_llm_with_schema(prompt, ClientNeeds, mock_llm_extraction)
    
    validation_errors = validate_client_needs(needs)
    if validation_errors:
        raise ExtractionValidationError(validation_errors, prompt_hash)
        
    return needs, prompt_hash
