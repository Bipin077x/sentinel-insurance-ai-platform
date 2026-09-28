import json
import random

def generate_synthetic_clients():
    clients_raw = []
    ground_truths = []
    
    # 6 clear-fit cases
    # 2 Basic
    clients_raw.append({"client_id": "CLIENT-1001", "raw_text": "I need the cheapest possible medical coverage for a 7-day trip to Mexico. I'm young and healthy. No trip cancellation needed."})
    ground_truths.append({"client_id": "CLIENT-1001", "expected_recommendation": ["prod_basic"], "type": "clear-fit"})
    clients_raw.append({"client_id": "CLIENT-1002", "raw_text": "Budget is tight, just going to Canada for the weekend. Just emergency medical, no extreme sports."})
    ground_truths.append({"client_id": "CLIENT-1002", "expected_recommendation": ["prod_basic"], "type": "clear-fit"})
    
    # 2 Standard
    clients_raw.append({"client_id": "CLIENT-1003", "raw_text": "My wife and I want standard medical and some trip cancellation for our 14-day cruise to the Bahamas. We want a moderate price."})
    ground_truths.append({"client_id": "CLIENT-1003", "expected_recommendation": ["prod_standard"], "type": "clear-fit"})
    clients_raw.append({"client_id": "CLIENT-1004", "raw_text": "Standard coverage for a 10-day trip to Europe. Nothing crazy, just museums."})
    ground_truths.append({"client_id": "CLIENT-1004", "expected_recommendation": ["prod_standard"], "type": "clear-fit"})
    
    # 1 Premium, 1 Adventure
    clients_raw.append({"client_id": "CLIENT-1005", "raw_text": "I need broad coverage for a 3-week luxury trip. I have diabetes (pre-existing) but I want the best coverage."})
    ground_truths.append({"client_id": "CLIENT-1005", "expected_recommendation": ["prod_premium"], "type": "clear-fit"})
    
    clients_raw.append({"client_id": "CLIENT-1006", "raw_text": "Going base jumping in Switzerland. I know it's a high-risk activity, so I need extreme sports coverage."})
    ground_truths.append({"client_id": "CLIENT-1006", "expected_recommendation": ["prod_adventure"], "type": "clear-fit"})

    # 4 Filter cases (otherwise appealing product gets excluded)
    # Case 1: Wants cheap (Basic) but has pre-existing conditions
    clients_raw.append({"client_id": "CLIENT-1007", "raw_text": "I need the lowest cost basic plan for 10 days in Japan. By the way, I have a pre-existing heart condition."})
    ground_truths.append({"client_id": "CLIENT-1007", "expected_recommendation": ["prod_standard", "prod_premium"], "excluded": "prod_basic", "type": "filter"})
    
    # Case 2: Wants Standard but doing extreme sports
    clients_raw.append({"client_id": "CLIENT-1008", "raw_text": "Looking for a mid-priced standard plan for a week in the Alps. We will be heli-skiing every day."})
    ground_truths.append({"client_id": "CLIENT-1008", "expected_recommendation": ["prod_adventure"], "excluded": "prod_standard", "type": "filter"})
    
    # Case 3: Wants Premium but doing base jumping (Premium excludes base jumping)
    clients_raw.append({"client_id": "CLIENT-1009", "raw_text": "I want the premium high-limit plan for broad coverage in New Zealand. I'll be doing some base jumping."})
    ground_truths.append({"client_id": "CLIENT-1009", "expected_recommendation": ["prod_adventure"], "excluded": "prod_premium", "type": "filter"})

    # Case 4: Wants Budget (Basic) but wants trip cancellation
    clients_raw.append({"client_id": "CLIENT-1010", "raw_text": "Need a really low cost budget plan, but I MUST have trip cancellation because my flights were expensive."})
    ground_truths.append({"client_id": "CLIENT-1010", "expected_recommendation": ["prod_standard", "prod_premium"], "excluded": "prod_basic", "type": "filter"})

    # 5 Ambiguous cases (Multiple acceptable options)
    clients_raw.append({"client_id": "CLIENT-1011", "raw_text": "Not sure what I want. Just going to Mexico for a week. Don't want to spend too much but want to feel safe."})
    ground_truths.append({"client_id": "CLIENT-1011", "expected_recommendation": ["prod_basic", "prod_standard"], "type": "ambiguous"})
    
    clients_raw.append({"client_id": "CLIENT-1012", "raw_text": "Taking the family to Hawaii. We'd like some cancellation coverage but we aren't rich."})
    ground_truths.append({"client_id": "CLIENT-1012", "expected_recommendation": ["prod_standard", "prod_premium"], "type": "ambiguous"})
    
    clients_raw.append({"client_id": "CLIENT-1013", "raw_text": "Going hiking in Peru. Need medical. No pre-existing conditions."})
    ground_truths.append({"client_id": "CLIENT-1013", "expected_recommendation": ["prod_basic", "prod_standard"], "type": "ambiguous"})
    
    clients_raw.append({"client_id": "CLIENT-1014", "raw_text": "I'm a digital nomad traveling for 3 months. I want decent coverage, price doesn't matter too much but I don't need excessive limits."})
    ground_truths.append({"client_id": "CLIENT-1014", "expected_recommendation": ["prod_standard", "prod_premium"], "type": "ambiguous"})
    
    clients_raw.append({"client_id": "CLIENT-1015", "raw_text": "Just looking for standard travel insurance for a weekend trip."})
    ground_truths.append({"client_id": "CLIENT-1015", "expected_recommendation": ["prod_basic", "prod_standard"], "type": "ambiguous"})

    # 1 Bad synthetic data for validator test
    clients_raw.append({
        "client_id": "CLIENT-BAD-1001",
        "raw_text": "I'm traveling to Mars for -5 days. Need coverage for extreme sports.",
        "metadata": {"submission_date": "2026-09-23T10:00:00Z"}
    })
    ground_truths.append({
        "client_id": "CLIENT-BAD-1001",
        "expected_recommendation": ["extraction_failed"], "type": "bad"
    })
    
    with open("synthetic_clients.json", "w") as f:
        json.dump(clients_raw, f, indent=2)
        
    with open("brokerage_ground_truth.json", "w") as f:
        json.dump(ground_truths, f, indent=2)
        
    print("Generated 15 synthetic client profiles + 1 bad profile.")

if __name__ == "__main__":
    generate_synthetic_clients()
