from typing import List, Dict, Tuple
from core.models import CatalogProduct, ClientNeeds

ACTIVITY_TAXONOMY = {
    "heli-skiing": ["extreme sports", "high-risk activities"],
    "base jumping": ["extreme sports", "high-risk activities"],
    "cliff diving": ["extreme sports", "high-risk activities"],
    "wingsuit flying": ["extreme sports", "high-risk activities"],
    "high-altitude trekking": ["extreme sports", "high-risk activities"],
    "scuba diving": ["high-risk activities"]
}

def filter_eligible_products(
    client_needs: ClientNeeds, 
    catalog: List[CatalogProduct]
) -> Tuple[List[CatalogProduct], Dict[str, str]]:
    """
    Deterministically filters out products that do not cover the client's stated needs.
    Returns:
      - List of eligible products
      - Dictionary mapping excluded product_id to reason
    """
    eligible = []
    excluded = {}

    for product in catalog:
        reasons = []
        
        # Check exclusions against activities using taxonomy
        for activity in client_needs.activities:
            activity_categories = [activity.lower()] + ACTIVITY_TAXONOMY.get(activity.lower(), [])
            for category in activity_categories:
                if any(category in exclusion.lower() for exclusion in product.exclusion_list):
                    reasons.append(f"Excluded activity: {activity}")
                    break
                
        # Check exclusions against pre-existing conditions
        if client_needs.pre_existing_conditions:
            if any("pre-existing" in exclusion for exclusion in product.exclusion_list):
                reasons.append("Excluded: pre-existing conditions")
                
        # Check exclusions against destination
        if any(client_needs.destination.lower() in exclusion.lower() for exclusion in product.exclusion_list):
            reasons.append(f"Excluded destination: {client_needs.destination}")
            
        # Check exclusions against coverage priorities
        for priority in client_needs.coverage_priorities:
            if any(priority in exclusion for exclusion in product.exclusion_list):
                reasons.append(f"Excluded coverage: {priority}")
                
        if reasons:
            excluded[product.product_id] = " | ".join(reasons)
        else:
            eligible.append(product)

    return eligible, excluded
