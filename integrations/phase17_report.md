# Phase 17 — Realistic Integration Adapter (Item 3, Generic Legacy Contract)

## ⚠️ DISCLAIMER
**This phase validates the adapter's ability to handle realistic FAILURE MODES common to legacy insurance integrations (async writes, partial failures, idempotency). It does NOT validate compatibility with any specific named vendor's actual API (e.g., Guidewire, Duck Creek), since no real vendor documentation was used in building this contract.**

## Test: Realistic Legacy Adapter Integration Patterns
**Actual output:**
```
--- 1. Round-Trip XML Translation Test ---
Generated XML:
<PolicyUpdate><ApplicationId>APP-999</ApplicationId><Decision>accept</Decision><ConfidenceScore>0.95</ConfidenceScore><ReasoningText>Standard risk profile</ReasoningText><Status>auto_decided</Status></PolicyUpdate>
Parsed Outcome: accept == accept
Parsed Subject: APP-999 == APP-999
Parsed Confidence: 0.95 == 0.95
Parsed Status: DecisionStatus.AUTO_DECIDED == DecisionStatus.AUTO_DECIDED
-> XML Round-trip passed exactly.

--- 2. Idempotency Test (Network Retry / Double-Apply Check) ---
Backend Apply Count before adapter call: 0
Backend Apply Count after adapter internally retried 503: 1
Change in Apply Count: 1 (should be exactly 1 despite retry)
-> Idempotency logic correctly prevented double-application during network retries.

--- 3. Partial Failure Test & Review Queue Routing ---
Success returned: False
New Decision Status: DecisionStatus.PENDING_REVIEW
New Reasoning Text: Standard risk profile
Integration Partial Failure: {"PolicyAdmin": "SUCCESS", "Billing": "FAILED - Timeout"}
Backend hit count for this operation: 1
-> Partial failure cleanly caught, explicitly logged to review queue, and NOT blindly retried.

--- 4. Timeout Test & Review Queue Routing ---
New Decision Status: DecisionStatus.PENDING_REVIEW
New Reasoning Text: Standard risk profile
Integration Timeout: Timed out waiting for job 2f2c68d7-c600-4287-8b33-3c624b031bf8 to confirm
Backend hit count for this operation: 1
-> Timeout case correctly pushed decision into unconfirmed/review state.
```
**Result:** Pass
