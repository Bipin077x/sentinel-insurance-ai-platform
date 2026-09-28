import json
import random

def generate_population(group_b_share: int, group_a_share: int, prefix: str):
    apps = []
    total_apps = 200
    high_cost_total = 60
    low_cost_total = 140
    
    # Calculate how many high cost go to B and A
    high_cost_b = int((group_b_share / 100.0) * high_cost_total)
    high_cost_a = high_cost_total - high_cost_b
    
    # Calculate how many low cost go to B and A to keep group sizes exactly 100 each
    low_cost_b = 100 - high_cost_b
    low_cost_a = 100 - high_cost_a
    
    id_counter = 1
    
    def add_apps(group, is_high_cost, count):
        nonlocal id_counter
        for _ in range(count):
            trip_cost = random.randint(5000, 10000) if is_high_cost else random.randint(1000, 4999)
            age = random.randint(30, 45) # safe age
            
            apps.append({
                "app_id": f"{prefix}-{id_counter:03d}",
                "age": age,
                "destination": "France", # safe destination recognized by extractor
                "trip_duration_days": 7,
                "trip_cost": float(trip_cost),
                "pre_existing_conditions": False,
                "planned_activities": ["swimming", "sightseeing"],
                "raw_text": f"I am {age} years old. I am going to France for 7 days. The cost is ${trip_cost}.",
                "metadata": {
                    "demographic_group": group,
                    "submission_date": "2026-09-26T10:00:00Z"
                }
            })
            id_counter += 1

    add_apps("Group B", True, high_cost_b)
    add_apps("Group A", True, high_cost_a)
    add_apps("Group B", False, low_cost_b)
    add_apps("Group A", False, low_cost_a)
    
    random.shuffle(apps)
    
    with open("synthetic_applications.json", "w") as f:
        json.dump(apps, f, indent=2)
        
    print(f"Generated {len(apps)} apps with high-cost split B:{group_b_share}/A:{group_a_share}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python generate_correlated_population.py <B_share> <A_share> <prefix>")
        sys.exit(1)
    
    generate_population(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
