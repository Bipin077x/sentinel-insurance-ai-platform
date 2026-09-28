# Underwriting Real-Data Source

## Dataset: Travel Insurance Claim Status Prediction (AXA)

- **Source:** Kaggle / GitHub (`https://raw.githubusercontent.com/juschan/ml_travelclaims/master/travel%20insurance.csv`)
- **Size:** ~63,000 records
- **Description:** A third-party dataset containing actual travel insurance policies and their eventual claim status.

## Explicit Mapping & Limitations

This dataset is used to validate the stratification capability of `risk_scoring.py`. It is explicitly NOT used for fraud detection or accept/decline validation.

**Mapped Fields:**
- `Age` -> `app.age`
- `Duration` -> `app.trip_duration_days`
- `Destination` -> `app.destination`
- `Net Sales` -> `app.trip_cost` (Note: Net Sales represents the premium/sales amount paid, which acts as a proxy for the total trip cost in our algorithm. This is an approximation, as premium is usually a fraction of trip cost.)

**Unmapped / Untestable Fields:**
- `pre_existing_conditions`: There is no equivalent field in this dataset. As a result, the `pre_existing_conditions` multiplier in `risk_scoring.py` (+0.75) is entirely untested by this phase. We assume `False` for all real records.
- `planned_activities`: There is no equivalent field for risky activities (skiing, scuba diving). We assume an empty list for all real records.

**Target Variable:**
- `Claim` (Yes/No): Represents whether a claim was eventually made. Used to test if the assigned Risk Tier accurately predicts claim likelihood.
