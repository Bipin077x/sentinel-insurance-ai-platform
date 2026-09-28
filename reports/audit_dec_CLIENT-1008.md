# Case Audit Report: dec_CLIENT-1008

**Subject ID:** CLIENT-1008
**Function Type:** brokerage
**Final Outcome:** recommendation
**Status:** auto_decided

## 1. Input Data & Redaction
```json
{
  "client_needs": {
    "client_id": "CLIENT-1008",
    "destination": "Alps",
    "duration_days": 7,
    "coverage_priorities": [
      "medical"
    ],
    "activities": [
      "heli-skiing"
    ],
    "pre_existing_conditions": false,
    "budget_signal": "standard"
  },
  "eligible_catalog": [
    {
      "product_id": "prod_adventure",
      "name": "Adventure-Sport Add-on",
      "base_price": 200.0,
      "features": [
        "Specific high-risk activities covered",
        "Extreme sports coverage",
        "Evacuation"
      ],
      "eligibility_rules": {},
      "exclusion_list": [
        "pre-existing conditions"
      ]
    }
  ],
  "excluded_catalog": {
    "prod_basic": "Excluded activity: heli-skiing",
    "prod_standard": "Excluded activity: heli-skiing",
    "prod_premium": "Excluded activity: heli-skiing"
  },
  "llm_self_reported_confidence": 0.95,
  "consistency_label": "High Confidence"
}
```
> **Note:** Redacted values (e.g., names, SSNs) appear as `[REDACTED]`. The raw, unredacted data is stored securely under a 30-day retention policy in the `raw_documents` table.

## 2. Rule Evaluation
```json
{
  "excluded": {
    "prod_basic": "Excluded activity: heli-skiing",
    "prod_standard": "Excluded activity: heli-skiing",
    "prod_premium": "Excluded activity: heli-skiing"
  },
  "recommended": "prod_adventure"
}
```

## 3. Escalation & Overrides
**Override Mechanism Fired:** None

## 4. Model Confidence & Calibration
**Confidence Score:** 1.0
**Confidence Source:** `semantic_consistency_n5`
> **Note:** This confidence score represents semantic self-consistency across multiple sampled generations, not an absolute probability of correctness.

## 5. Reasoning & Faithfulness
**Reasoning Text:**
> Based on needs, prod_adventure is the best fit.

**Faithfulness Check:** [PASSED]

## 6. Cryptographic Integrity (Live Verification)
**Verification Timestamp:** 2026-09-23T09:06:46.246540+00:00
**Chain Verification Status:** PASSED
**Model Version Pinned:** mock-llm-1.0-0613
**Compliance Ruleset Hash Active:** e497a7e026cf20e1874aadc4b8135a1fd08a278fb6b9b27a53a7a5d90681cac4
**Prompt Hash Active:** b15b934bae723a75d220cb48979e0cf49055bc71532bbc99466075651e269283
