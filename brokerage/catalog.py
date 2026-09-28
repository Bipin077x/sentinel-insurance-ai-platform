from core.models import CatalogProduct

def get_catalog():
    return [
        CatalogProduct(
            product_id="prod_basic",
            name="Basic",
            base_price=30.0,
            features=["Low cost", "Emergency medical"],
            eligibility_rules={},
            exclusion_list=["pre-existing conditions", "high-risk activities", "trip cancellation"]
        ),
        CatalogProduct(
            product_id="prod_standard",
            name="Standard",
            base_price=75.0,
            features=["Moderate coverage", "Standard medical", "Trip cancellation"],
            eligibility_rules={},
            exclusion_list=["pre-existing conditions", "extreme sports"]
        ),
        CatalogProduct(
            product_id="prod_premium",
            name="Premium",
            base_price=150.0,
            features=["Broad coverage", "High limits", "Pre-existing condition coverage (with waiting period)"],
            eligibility_rules={},
            exclusion_list=["high-altitude trekking", "base jumping", "heli-skiing", "wingsuit flying"]
        ),
        CatalogProduct(
            product_id="prod_adventure",
            name="Adventure-Sport Add-on",
            base_price=200.0,
            features=["Specific high-risk activities covered", "Extreme sports coverage", "Evacuation"],
            eligibility_rules={},
            exclusion_list=["pre-existing conditions"]
        )
    ]
