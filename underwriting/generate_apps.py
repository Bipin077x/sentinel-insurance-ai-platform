import json
import random

def generate_synthetic_applications():
    apps_raw = []
    ground_truths = []
    
    for i in range(1, 26):
        app_id = f"APP-{1000+i}"
        
        # Scenarios
        # 1-8: clear-accept
        # 9-16: clear-decline
        # 17-21: referral-designed
        # 22-25: ambiguous premium-pricing
        
        if i <= 8:
            # Clear Accept
            age = random.randint(20, 50)
            dest = "France"
            cost = random.randint(1000, 3000)
            pre_existing = False
            duration = 14
            activities = ["sightseeing", "museums"]
            gt = "accept"
            raw_text = f"I am {age} years old traveling to {dest} for {duration} days. Trip cost is ${cost}. No pre-existing medical conditions. Just doing {', '.join(activities)}."
            category = "clear-accept"
        elif i <= 16:
            # Clear Decline - Alternate reasons
            reason_type = i % 3
            if reason_type == 0: # Age
                age = 88
                dest = "Italy"
                cost = 2000
                pre_existing = False
                activities = ["walking"]
            elif reason_type == 1: # Destination
                age = 35
                dest = "North Korea"
                cost = 2000
                pre_existing = False
                activities = ["guided tour"]
            else: # Activity
                age = 28
                dest = "Switzerland"
                cost = 1500
                pre_existing = False
                activities = ["base jumping", "heli-skiing"]
                
            duration = 10
            gt = "decline"
            raw_text = f"I am {age} years old traveling to {dest} for {duration} days. Trip cost is ${cost}. Pre-existing conditions: {pre_existing}. Activities: {', '.join(activities)}."
            category = "clear-decline"
        elif i <= 21:
            # Referral-designed (passes rules individually, triggers override)
            if i % 2 == 0:
                # Treaty Limit override
                age = 35
                dest = "Canada"
                cost = 12000 # High sum insured
                pre_existing = False
                activities = ["sightseeing"]
                raw_text = f"I am {age} years old traveling to {dest} for 10 days. Trip cost is ${cost}. No pre-existing conditions. Activities: {', '.join(activities)}."
            else:
                # Factor stacking (age 74 + high risk dest USA + pre-existing)
                age = 74
                dest = "USA"
                cost = 3000
                pre_existing = True
                activities = ["walking"]
                raw_text = f"I am {age} years old traveling to {dest} for 10 days. Trip cost is ${cost}. I have pre-existing conditions. Activities: {', '.join(activities)}."
            gt = "refer"
            category = "referral-designed"
        else:
            # Ambiguous premium-pricing
            age = 45
            dest = "Switzerland"
            cost = 8000
            pre_existing = True
            duration = 21
            activities = ["skiing", "hiking"]
            gt = "review"
            raw_text = f"I am {age} years old traveling to {dest} for {duration} days. Trip cost is ${cost}. I do have some pre-existing conditions. Planning on {', '.join(activities)}."
            category = "ambiguous-pricing"

        # Deliberate Proxy Bias Injection:
        # Group B predominantly gets decline and referral.
        # Group A predominantly gets accept.
        if category in ["clear-decline", "referral-designed"]:
            demo_group = "Group B" if random.random() < 0.8 else "Group A"
        else:
            demo_group = "Group A" if random.random() < 0.8 else "Group B"

        apps_raw.append({
            "app_id": app_id,
            "raw_text": raw_text,
            "metadata": {
                "submission_date": "2026-09-23T10:00:00Z",
                "demographic_group": demo_group
            }
        })
        
        ground_truths.append({
            "app_id": app_id,
            "expected_outcome": gt,
            "category": category
        })
        
    # Inject bad synthetic data to test deterministic fallback validation
    bad_app_1 = {
        "app_id": "APP-BAD-1001",
        "raw_text": "I am 400 years old traveling to Mars for 10 days. Trip cost is $2500. No pre-existing medical conditions. Just doing sightseeing. Email me at bad.guy@example.com",
        "metadata": {
            "submission_date": "2026-09-23T10:00:00Z"
        }
    }
    bad_app_2 = {
        "app_id": "APP-BAD-1002",
        "raw_text": "I am 30 years old traveling to Japan for 10 days. Trip cost is $-100. No pre-existing medical conditions.",
        "metadata": {
            "submission_date": "2026-09-23T10:00:00Z"
        }
    }
    apps_raw.extend([bad_app_1, bad_app_2])
    
    ground_truths.extend([
        {"app_id": "APP-BAD-1001", "expected_outcome": "extraction_failed"},
        {"app_id": "APP-BAD-1002", "expected_outcome": "extraction_failed"}
    ])
        
    with open("synthetic_applications.json", "w") as f:
        json.dump(apps_raw, f, indent=2)
        
    with open("underwriting_ground_truth.json", "w") as f:
        json.dump(ground_truths, f, indent=2)
        
    print("Generated 25 synthetic applications and 2 bad applications.")

if __name__ == "__main__":
    generate_synthetic_applications()
