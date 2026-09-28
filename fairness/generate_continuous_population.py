import json
import random

def generate_population(b_share: int, a_share: int, prefix: str):
    apps = []
    total_apps = 200
    
    # We want the overall high-risk trait (age > 50) to represent 30% of the population (60 apps)
    # just like Phase 16, so the math is identical for comparison.
    high_risk_total = 60
    
    high_risk_b = int((b_share / 100.0) * high_risk_total)
    high_risk_a = high_risk_total - high_risk_b
    
    low_risk_b = 100 - high_risk_b
    low_risk_a = 100 - high_risk_a
    
    id_counter = 1
    
    def add_apps(group, is_high_risk, count):
        nonlocal id_counter
        for _ in range(count):
            # Continuously sample age.
            # If high_risk, age > 50 (sampled 51-80)
            # If low_risk, age <= 50 (sampled 25-50)
            age = random.randint(51, 80) if is_high_risk else random.randint(25, 50)
            
            # Safe trip cost and destination so they don't trigger the binary referral threshold
            trip_cost = random.randint(1000, 4999) 
            
            apps.append({
                "app_id": f"{prefix}-{id_counter:03d}",
                "age": age,
                "destination": "France",
                "trip_duration_days": 7,
                "trip_cost": float(trip_cost),
                "pre_existing_conditions": True,  # Interacts with age > 50 to cause High Risk tier
                "planned_activities": ["swimming", "sightseeing"],
                "raw_text": f"I am {age} years old. I am going to France for 7 days. The cost is ${trip_cost}. Note: I have a pre-existing medical condition.",
                "metadata": {
                    "demographic_group": group,
                    "submission_date": "2026-09-26T10:00:00Z"
                }
            })
            id_counter += 1

    add_apps("Group B", True, high_risk_b)
    add_apps("Group A", True, high_risk_a)
    add_apps("Group B", False, low_risk_b)
    add_apps("Group A", False, low_risk_a)
    
    random.shuffle(apps)
    
    with open("synthetic_applications.json", "w") as f:
        json.dump(apps, f, indent=2)

if __name__ == "__main__":
    import sys
    generate_population(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
