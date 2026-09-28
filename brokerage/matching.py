from typing import List
from core.models import ClientNeeds, CatalogProduct

def filter_eligible_products(needs: ClientNeeds, catalog: List[CatalogProduct]) -> List[CatalogProduct]:
    eligible = []
    
    for prod in catalog:
        rules = prod.eligibility_rules
        
        # 1. Max Duration Check
        if needs.duration_days > rules.get("max_duration_days", 365):
            continue
            
        # 2. Excluded Regions Check
        # For simplicity, just checking if needs.destination matches an excluded region
        if needs.destination in rules.get("excluded_regions", []):
            continue
            
        eligible.append(prod)
        
    return eligible
