import pandas as pd
import json

def load_axa_data(csv_path: str = "data/axa_travel_insurance.csv"):
    df = pd.read_csv(csv_path)
    
    apps = []
    
    for idx, row in df.iterrows():
        # Map fields explicitly
        age = int(row['Age']) if pd.notnull(row['Age']) else 35
        duration = int(row['Duration']) if pd.notnull(row['Duration']) else 7
        destination = str(row['Destination'])
        net_sales = float(row['Net Sales']) if pd.notnull(row['Net Sales']) else 0.0
        
        # In our model, base_premium = trip_cost * 0.05.
        # Net Sales represents premium paid.
        # So trip_cost = Net Sales / 0.05 = Net Sales * 20
        # Wait, if Net Sales is negative (refunds), we cap at 0
        net_sales = max(0.0, net_sales)
        trip_cost = net_sales * 20.0
        
        # Target
        claim_made = (str(row['Claim']).strip().upper() == 'YES')
        
        # Explicitly unmapped / untestable fields are defaulted
        app = {
            "id": f"AXA-{idx:05d}",
            "age": age,
            "destination": destination,
            "trip_duration_days": duration,
            "trip_cost": trip_cost,
            "pre_existing_conditions": False,  # UNMAPPED
            "planned_activities": [],          # UNMAPPED
            "metadata": {
                "claim_target": claim_made
            }
        }
        apps.append(app)
        
    return apps

if __name__ == "__main__":
    apps = load_axa_data()
    claims = sum(1 for a in apps if a["metadata"]["claim_target"])
    print(f"Loaded {len(apps)} applications.")
    print(f"Total claims: {claims}")
    print(f"Base claim rate: {claims / len(apps):.2%}")
    
    with open("data/real_axa_underwriting.json", "w") as f:
        json.dump(apps, f, indent=2)
