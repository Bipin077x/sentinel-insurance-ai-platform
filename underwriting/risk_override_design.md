# Underwriting Risk Override Design

## 1. Systematic Confident-Wrong-ness in Underwriting
In claims processing, an LLM could confidently (and self-consistently) deny a claim for failing a hard rule, while remaining completely blind to the fact that the claim had a perfect 1.0 fraud score requiring human investigation.

In underwriting, a similar blind spot occurs when an application technically passes all eligibility rules individually, but the *combination* of factors represents a complex, asymmetric risk that should not be auto-priced or auto-approved. An LLM might look at an application and reason: "Age is within limits, destination is not excluded, activity is not excluded -> Confidently approve and price."

**Examples of LLM Blind Spots:**
1. **Risk Concentration (Borderline Factor Stacking):** An applicant might be just under the age limit (e.g., 74, limit 75), traveling to a high-cost medical destination (e.g., USA), requesting a very high sum insured ($45,000, limit $50,000), and planning activities that are *almost* extreme sports (e.g., amateur motorcycle touring). Individually, these pass. Jointly, the actuarial risk is extreme. The LLM will consistently approve this because it thinks logically (A is true, B is true -> Output is true), rather than actuarially (A is 90th percentile, B is 95th percentile -> tail risk).
2. **Reinsurance/Treaty Triggers:** Regulatory or reinsurance treaties often mandate human referral for exposures above a certain absolute monetary value, regardless of how safe the applicant is. An LLM might confidently price a $10M policy for a 20-year-old traveling to Canada because the applicant risk is low, completely ignoring the operational treaty mandate that says "Anything over $2M goes to the desk."
3. **Watchlist / Sanctions Matches:** The applicant's name or details closely match an OFAC or internal watchlist entity. The LLM might confidently approve the travel policy because the trip details are benign.

## 2. Deterministic `referral_score` Signal
To prevent the LLM from auto-approving these complex cases, we will implement `referral_score.py`, which computes a deterministic `referral_score` (0.0 to 1.0) and a list of triggered criteria, entirely bypassing the LLM. 

**Criteria:**
- **High Exposure (Treaty Limit):** If `sum_insured` >= $5,000 (for this POC). -> +1.0 (Instant Referral)
- **Factor Stacking:** 
  - Age >= 70 -> +0.4
  - High-risk destination (e.g., USA, Switzerland) -> +0.4
  - Pre-existing condition -> +0.4
  - If sum of factor stacking >= 0.8 (e.g., older age + high risk destination) -> Override triggers.
- **Watchlist Flags:** Any known flagged entity/name -> +1.0

If `referral_score` >= 0.8, the application is forced into the human `PENDING_REVIEW` queue, completely ignoring the LLM's `calibrated_confidence` score. This will be enforced in `gate.py`.
