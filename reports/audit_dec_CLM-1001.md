# Case Audit Report: dec_CLM-1001

**Subject ID:** CLM-1001
**Function Type:** claims
**Final Outcome:** deny
**Status:** auto_decided

## 1. Input Data & Redaction
```json
{
  "claim": {
    "id": "CLM-1001",
    "policy_id": "POL-1001",
    "date_filed": "2026-09-21T21:03:59.180063Z",
    "incident_date": "2026-09-21T21:03:59.180063Z",
    "claim_type": "trip_cancellation",
    "amount": 2119.69,
    "cause": "airline bankruptcy",
    "evidence_list": []
  },
  "fraud_score": 0.0,
  "fraud_flags": [],
  "llm_self_reported_confidence": 0.98
}
```
> **Note:** Redacted values (e.g., names, SSNs) appear as `[REDACTED]`. **The raw, unredacted data has been PERMANENTLY DELETED per the configured retention policy.**

## 2. Rule Evaluation
```json
{
  "policy_exists": false
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
> Claim denied due to failing rules: policy_exists.


**Faithfulness Check:** [PASSED]

## 6. Cryptographic Integrity (Live Verification)
**Verification Timestamp:** 2026-09-26T09:38:11.137569+00:00
**Chain Verification Status:** PASSED
**Model Version Pinned:** mock-llm-1.0-0613
**Compliance Ruleset Hash Active:** e497a7e026cf20e1874aadc4b8135a1fd08a278fb6b9b27a53a7a5d90681cac4
**Prompt Hash Active:** 578c8faa4490e3a2babd62f25ff45618618009db270b1853ee51a833b2bed998
