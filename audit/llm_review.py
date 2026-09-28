"""
audit/llm_review.py — Calibrated LLM-assisted audit review.

For each statistically flagged item, pulls the full decision trail and asks
the LLM for a plain-language contextual assessment. The finding's cited_evidence
is verified by faithfulness.py — same fabrication-prevention standard as every
other LLM-touching stage. The call is calibrated via semantic entropy; low
agreement forces recommended_action to "needs_senior_review."
"""

import json
from typing import List, Optional, Tuple
from pydantic import BaseModel
from typing import Literal

from core.llm_client import call_llm_with_schema
from core.prompt_registry import load_prompt
from core.calibration import compute_semantic_entropy
from audit.anomaly_detection import AnomalyFlag


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class AuditFinding(BaseModel):
    is_supported:          bool
    inconsistencies_found: bool
    cited_evidence:        List[str]      # Must be verifiable against inputs_snapshot/rule_results
    recommended_action:    Literal["escalate", "dismiss_benign", "needs_senior_review"]
    audit_rationale:       str


# ---------------------------------------------------------------------------
# Faithfulness verification for audit findings
# ---------------------------------------------------------------------------

def verify_audit_finding_faithfulness(
    finding:         AuditFinding,
    inputs_snapshot: dict,
    rule_results:    dict,
) -> List[str]:
    """
    Verifies that every item in cited_evidence maps to an actual key in the
    decision's inputs_snapshot or rule_results.

    Accepts top-level keys and one-level dotted paths (e.g. "claim.amount"
    where "claim" is a top-level key in inputs_snapshot).
    """
    errors = []

    # Build the full set of verifiable references
    available: set = set()

    # Top-level inputs_snapshot keys
    for k, v in inputs_snapshot.items():
        available.add(k.lower())
        # One-level dotted paths for nested dicts
        if isinstance(v, dict):
            for subk in v.keys():
                available.add(f"{k.lower()}.{subk.lower()}")

    # Rule results keys
    for k in rule_results.keys():
        available.add(k.lower())

    for evidence_item in finding.cited_evidence:
        if evidence_item.lower() not in available:
            errors.append(
                f"Fabrication detected: cited_evidence '{evidence_item}' does not "
                f"exist in the decision's inputs_snapshot or rule_results. "
                f"Available keys: {sorted(available)}"
            )

    return errors


# ---------------------------------------------------------------------------
# Mock LLM — context-aware, varies by anomaly type and decision data
# ---------------------------------------------------------------------------

def _mock_audit_llm(
    prompt:           str,
    schema,
    flag:             AnomalyFlag,
    decision_data:    dict,
    inputs_snapshot:  dict,
    rule_results:     dict,
) -> str:
    """
    Mock auditor LLM. Produces realistic, varying responses based on:
    - The detector type (anomaly_flag.detector)
    - Signals in the inputs_snapshot and rule_results

    NEGATIVE CASE (benign): decisions with subject_id containing "LEGIT" and
    all rule_results True → recommended_action = "dismiss_benign"
    """
    decision = decision_data.get("decision")
    subject_id = decision.subject_id if decision else ""
    detector = flag.detector

    # Determine available evidence keys for citing
    available_keys = list(inputs_snapshot.keys())
    claim_keys = []
    if "claim" in inputs_snapshot and isinstance(inputs_snapshot["claim"], dict):
        claim_keys = [f"claim.{k}" for k in inputs_snapshot["claim"].keys()]

    all_rules_passed = all(v for v in rule_results.values() if isinstance(v, bool))

    # --- Routing logic ---

    # Legitimate large claim (negative case): all rules passed, "LEGIT" in subject_id
    if "LEGIT" in subject_id and all_rules_passed:
        return json.dumps({
            "is_supported": True,
            "inconsistencies_found": False,
            "cited_evidence": (["claim", "claim.amount"] + list(rule_results.keys())[:2])[:4],
            "recommended_action": "dismiss_benign",
            "audit_rationale": (
                f"The statistical outlier ({flag.description[:80]}...) reflects a "
                f"legitimately large but well-documented claim. All deterministic rules "
                f"passed and rule_results show full coverage verification. The amount is "
                f"high but proportionate to the documented incident scope. Dismiss as benign."
            ),
        })

    # Fraud ring / timing cluster
    if detector == "timing_anomaly" or "FRAUD_RING" in subject_id:
        cite = (["claim", "claim.policy_id"] if claim_keys else available_keys[:2])
        return json.dumps({
            "is_supported": False,
            "inconsistencies_found": True,
            "cited_evidence": cite[:3],
            "recommended_action": "escalate",
            "audit_rationale": (
                f"Timing pattern is highly anomalous: {flag.description} "
                f"Multiple decisions from the same subject within a narrow window, "
                f"without independent corroborating documentation, is a known fraud-ring "
                f"indicator. Escalate to senior investigator."
            ),
        })

    # Near-duplicate
    if detector == "near_duplicate":
        cite = (["claim.policy_id", "claim.claim_type", "claim.amount"]
                if claim_keys else available_keys[:2])
        return json.dumps({
            "is_supported": False,
            "inconsistencies_found": True,
            "cited_evidence": [c for c in cite if c in available_keys or "." in c][:3],
            "recommended_action": "escalate",
            "audit_rationale": (
                f"Near-duplicate pattern detected: {flag.description} "
                f"Multiple claims sharing the same policy, type, and approximate amount "
                f"without distinct incident identifiers suggests potential double-filing. "
                f"Escalate for manual cross-reference against original claim documentation."
            ),
        })

    # Threshold clustering
    if detector == "threshold_clustering":
        cite = available_keys[:2]
        return json.dumps({
            "is_supported": True,
            "inconsistencies_found": False,
            "cited_evidence": cite,
            "recommended_action": "needs_senior_review",
            "audit_rationale": (
                f"Confidence clustering near threshold: {flag.description} "
                f"The individual decision reasoning appears supported, but the population "
                f"pattern warrants senior review. Threshold-clustered confidence scores "
                f"may indicate systematic prompt or input manipulation rather than genuine "
                f"uncertainty resolution."
            ),
        })

    # Amount outlier — generic (non-LEGIT)
    if detector == "amount_outlier":
        cite = (["claim", "claim.amount", "fraud_score"]
                if "fraud_score" in inputs_snapshot else ["claim", "claim.amount"])
        cite = [c for c in cite if c in available_keys or ("." in c and c.split(".")[0] in inputs_snapshot)]
        return json.dumps({
            "is_supported": True,
            "inconsistencies_found": False,
            "cited_evidence": cite[:3] if cite else available_keys[:2],
            "recommended_action": "needs_senior_review",
            "audit_rationale": (
                f"Statistical outlier: {flag.description} "
                f"The decision reasoning does not contradict the inputs, but the magnitude "
                f"of the amount relative to the peer group is sufficient to warrant a "
                f"senior reviewer confirming independent valuation documentation exists."
            ),
        })

    # Approval-rate anomaly or default
    cite = available_keys[:2]
    return json.dumps({
        "is_supported": True,
        "inconsistencies_found": False,
        "cited_evidence": cite,
        "recommended_action": "needs_senior_review",
        "audit_rationale": (
            f"Anomalous pattern flagged: {flag.description} "
            f"Individual decision appears supported by available data, but the "
            f"population-level pattern warrants senior review to rule out systematic drift."
        ),
    })


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def conduct_audit_review(
    flag:          AnomalyFlag,
    decision_data: dict,
) -> Tuple[AuditFinding, str, float, List[str]]:
    """
    LLM-assisted review of a flagged anomaly.

    Returns: (finding, prompt_hash, calibrated_confidence, faithfulness_errors)

    If calibrated_confidence < 0.6, recommended_action is forced to
    "needs_senior_review" — an uncertain audit finding should not be asserted.
    """
    decision   = decision_data.get("decision")
    audit_trail = decision_data.get("audit_trail")

    inputs_snapshot = audit_trail.inputs_snapshot if audit_trail else {}
    rule_results    = audit_trail.rule_results    if audit_trail else {}

    if isinstance(inputs_snapshot, str):
        inputs_snapshot = json.loads(inputs_snapshot)
    if isinstance(rule_results, str):
        rule_results = json.loads(rule_results)

    template, prompt_hash = load_prompt("audit_review", "v2")

    stat_basis_str = json.dumps(flag.statistical_basis, indent=2)

    prompt = (
        template
        .replace("{{anomaly_detector}}",   flag.detector)
        .replace("{{statistical_basis}}",  stat_basis_str)
        .replace("{{anomaly_description}}", flag.description)
        .replace("{{decision_id}}",         decision.id          if decision else "N/A")
        .replace("{{function_type}}",       str(decision.function_type) if decision else "N/A")
        .replace("{{outcome}}",             decision.outcome     if decision else "N/A")
        .replace("{{confidence_score}}",    str(decision.confidence_score) if decision else "N/A")
        .replace("{{status}}",              str(decision.status) if decision else "N/A")
        .replace("{{reasoning_text}}",      decision.reasoning_text if decision else "N/A")
        .replace("{{rules_fired}}",         ", ".join(decision.rules_fired) if decision else "N/A")
        .replace("{{inputs_snapshot}}",     json.dumps(inputs_snapshot, indent=2))
        .replace("{{rule_results}}",        json.dumps(rule_results, indent=2))
    )

    def _llm_caller():
        mock_fn = lambda p, schema: _mock_audit_llm(
            p, schema, flag, decision_data, inputs_snapshot, rule_results
        )
        finding = call_llm_with_schema(prompt, AuditFinding, mock_fn)
        return finding, prompt_hash

    finding, used_prompt_hash, calibrated_confidence, _ = compute_semantic_entropy(
        _llm_caller, num_samples=3
    )

    # Low-confidence audit finding must not be asserted — force senior review
    if calibrated_confidence < 0.6:
        finding = AuditFinding(
            is_supported=finding.is_supported,
            inconsistencies_found=finding.inconsistencies_found,
            cited_evidence=finding.cited_evidence,
            recommended_action="needs_senior_review",
            audit_rationale=(
                f"[CALIBRATION FLAG: agreement={calibrated_confidence:.0%} across samples — "
                f"forced to needs_senior_review] " + finding.audit_rationale
            ),
        )

    # Faithfulness check on cited_evidence
    faithfulness_errors = verify_audit_finding_faithfulness(
        finding, inputs_snapshot, rule_results
    )

    return finding, used_prompt_hash, calibrated_confidence, faithfulness_errors
