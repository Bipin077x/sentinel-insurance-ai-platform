"""
audit/anomaly_detection.py — Population-level statistical anomaly detection.

Five detectors, all deterministic (no LLM). Every flag cites specific decision IDs
and a numeric statistical basis (z-score, bin count, span, etc.). No flag without
a number attached.

Distinct from Phase 8's per-decision case audit. This module finds decisions
nobody has specifically looked at yet, by scanning the full population.
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from core.database import SessionLocal, DecisionRecord, AuditTrailRecord

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# How to extract a numeric "amount" from each pipeline's inputs_snapshot.
# Extend this when new pipelines are added.
AMOUNT_FIELD_PATHS: Dict[str, List[str]] = {
    "claims":       ["claim", "amount"],
    "underwriting": ["application", "trip_cost"],
}

# Auto-decide confidence thresholds per pipeline (must match gate.py / run_*.py policy).
# Used by the threshold-clustering detector.
CONFIDENCE_THRESHOLDS: Dict[str, float] = {
    "claims":       0.85,
    "underwriting": 0.90,
    "brokerage":    0.85,
}

# Fragment strings that identify test-fixture decisions to exclude from detection.
FIXTURE_ID_FRAGMENTS: Tuple[str, ...] = (
    "audit_", "CEILING_TEST", "TAMPER_TEST",
    "CEILING_SUBJECT", "TAMPER_SUBJECT",
)

# Thresholds
AMOUNT_OUTLIER_Z_THRESHOLD    = 2.5   # |z| > 2.5 ≈ 99th percentile (normal assumption)
THRESHOLD_CLUSTER_Z_THRESHOLD = 2.0   # bin count z-score for threshold-clustering
THRESHOLD_CLUSTER_MIN_COUNT   = 3     # minimum cluster count to flag
TIMING_CLUSTER_MIN_COUNT      = 3     # minimum decisions in window to flag
TIMING_WINDOW_HOURS           = 24
APPROVAL_ANOMALY_Z_THRESHOLD  = 2.0
MIN_GROUP_SIZE_FOR_ZSCORE     = 3     # below this, skip statistical tests


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AnomalyFlag:
    """
    A flagged pattern. Every flag has a numeric statistical_basis — no narrative-only flags.
    """
    decision_ids:      List[str]        # One or more decisions involved
    detector:          str              # Which detector produced this flag
    statistical_basis: Dict[str, Any]   # Numeric evidence (z-score, counts, etc.)
    description:       str              # Human-readable summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_fixture(decision_id: str) -> bool:
    return any(frag in decision_id for frag in FIXTURE_ID_FRAGMENTS)


def _extract_amount(inputs_snapshot: dict, pipeline: str) -> Optional[float]:
    """Walks the AMOUNT_FIELD_PATHS registry to extract a numeric amount."""
    path = AMOUNT_FIELD_PATHS.get(pipeline)
    if not path:
        return None
    obj = inputs_snapshot
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    try:
        return float(obj)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Detector 1 — Amount outliers (z-score per peer group)
# ---------------------------------------------------------------------------

def detect_amount_outliers(records: list) -> List[AnomalyFlag]:
    """
    Groups decisions by (pipeline, outcome) and computes z-score of amounts.
    Flags any decision whose |z| > AMOUNT_OUTLIER_Z_THRESHOLD.
    """
    flags = []
    groups: Dict[Tuple[str, str], List[Tuple[str, float]]] = defaultdict(list)

    for d, a in records:
        if _is_fixture(d.id):
            continue
        pipeline = d.function_type.value
        if pipeline not in AMOUNT_FIELD_PATHS:
            continue
        snap = json.loads(a.inputs_snapshot)
        amount = _extract_amount(snap, pipeline)
        if amount is None or amount <= 0:
            continue
        groups[(pipeline, d.outcome)].append((d.id, amount))

    for (pipeline, outcome), items in groups.items():
        if len(items) < MIN_GROUP_SIZE_FOR_ZSCORE:
            continue
        ids, amounts_list = zip(*items)
        amounts = np.array(amounts_list, dtype=float)
        mean   = float(np.mean(amounts))
        std    = float(np.std(amounts, ddof=1)) if len(amounts) > 1 else 0.0
        if std == 0:
            continue
        z_scores = (amounts - mean) / std

        for i, (did, amount) in enumerate(zip(ids, amounts_list)):
            z = float(z_scores[i])
            if abs(z) > AMOUNT_OUTLIER_Z_THRESHOLD:
                percentile = float(np.sum(amounts < amount) / len(amounts) * 100)
                flags.append(AnomalyFlag(
                    decision_ids=[did],
                    detector="amount_outlier",
                    statistical_basis={
                        "z_score":      round(z, 4),
                        "amount":       amount,
                        "group_mean":   round(mean, 2),
                        "group_std":    round(std, 2),
                        "group_size":   len(items),
                        "percentile":   round(percentile, 1),
                        "pipeline":     pipeline,
                        "outcome":      outcome,
                    },
                    description=(
                        f"Amount ${amount:,.2f} is {abs(z):.2f}σ from the peer mean "
                        f"${mean:,.2f} (σ=${std:,.2f}, n={len(items)}) "
                        f"for {pipeline}/{outcome} decisions. "
                        f"Percentile rank: {percentile:.0f}th."
                    ),
                ))
    return flags


# ---------------------------------------------------------------------------
# Detector 2 — Confidence clustering near auto-decide threshold (gaming signal)
# ---------------------------------------------------------------------------

def detect_threshold_clustering(records: list) -> List[AnomalyFlag]:
    """
    Flags suspicious concentration of confidence scores just above the auto-decide
    threshold for each pipeline. This pattern — many cases scoring [threshold,
    threshold+0.02] — is a known indicator of decision-system gaming.

    Method: bin confidence scores into 0.02-wide bins. Compute z-score of the
    target bin count vs. all other bins. Flag if z > THRESHOLD_CLUSTER_Z_THRESHOLD
    and count >= THRESHOLD_CLUSTER_MIN_COUNT.
    """
    flags = []

    for pipeline, threshold in CONFIDENCE_THRESHOLDS.items():
        pipeline_recs = [
            (d, a) for d, a in records
            if d.function_type.value == pipeline and not _is_fixture(d.id)
        ]
        if len(pipeline_recs) < 5:
            continue

        scores = np.array([d.confidence_score for d, _ in pipeline_recs])

        window_lo = threshold
        window_hi = threshold + 0.02
        in_window_ids = [d.id for d, _ in pipeline_recs
                         if window_lo <= d.confidence_score <= window_hi]

        if len(in_window_ids) < THRESHOLD_CLUSTER_MIN_COUNT:
            continue

        # Align bins so that window_lo is exactly a bin edge.
        # We want bins from roughly 0.70 to 1.02.
        # Calculate how many 0.02 steps to go down from window_lo to get near 0.70
        steps_down = int((window_lo - 0.70) / 0.02)
        start_bin = window_lo - (steps_down * 0.02)
        bin_edges = np.arange(start_bin, 1.03, 0.02)
        bin_counts, _ = np.histogram(scores, bins=bin_edges)

        # Find which bin corresponds to our window
        target_bin_idx = None
        for i in range(len(bin_edges) - 1):
            if abs(bin_edges[i] - window_lo) < 1e-5:
                target_bin_idx = i
                break
        if target_bin_idx is None:
            continue

        target_count = int(bin_counts[target_bin_idx])
        # Exclude the massive 1.0 confidence spike (last two bins) from background stats
        other_counts = np.concatenate([
            bin_counts[:target_bin_idx], 
            bin_counts[target_bin_idx + 1:-2]  # Exclude last two bins (>= 0.98)
        ])
        other_nonzero = other_counts[other_counts > 0]
        if len(other_nonzero) < 2:
            # If not enough background, just use mean=0, std=1 for the anomaly test
            mean_other, std_other = 0.0, 1.0
        else:
            mean_other = float(np.mean(other_nonzero))
            std_other  = float(np.std(other_nonzero, ddof=1))
            if std_other == 0:
                std_other = 1.0

        z = (target_count - mean_other) / std_other
        if z > THRESHOLD_CLUSTER_Z_THRESHOLD and target_count >= THRESHOLD_CLUSTER_MIN_COUNT:
            flags.append(AnomalyFlag(
                decision_ids=in_window_ids,
                detector="threshold_clustering",
                statistical_basis={
                    "pipeline":                    pipeline,
                    "threshold":                   threshold,
                    "window":                      [round(window_lo, 3), round(window_hi, 3)],
                    "count_in_window":             target_count,
                    "mean_count_other_bins":       round(mean_other, 2),
                    "std_other_bins":              round(std_other, 2),
                    "z_score":                     round(z, 4),
                    "total_decisions_in_pipeline": len(pipeline_recs),
                },
                description=(
                    f"{target_count} {pipeline} decisions have confidence in "
                    f"[{window_lo:.2f}, {window_hi:.2f}] — just above the {threshold} "
                    f"auto-decide threshold. z={z:.2f} vs. other bins "
                    f"(mean={mean_other:.1f}, σ={std_other:.1f}). "
                    f"Potential threshold-gaming pattern."
                ),
            ))
    return flags


# ---------------------------------------------------------------------------
# Detector 3 — Timing anomalies (submission clustering)
# ---------------------------------------------------------------------------

def detect_timing_anomalies(records: list) -> List[AnomalyFlag]:
    """
    Flags subject_ids with TIMING_CLUSTER_MIN_COUNT or more decisions
    within a TIMING_WINDOW_HOURS window.
    """
    flags = []
    by_subject: Dict[str, List[Tuple[str, datetime]]] = defaultdict(list)

    for d, a in records:
        if _is_fixture(d.id):
            continue
        ts = d.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        by_subject[d.subject_id].append((d.id, ts))

    reported_subjects = set()

    for subject_id, entries in by_subject.items():
        if subject_id in reported_subjects:
            continue
        if len(entries) < TIMING_CLUSTER_MIN_COUNT:
            continue
        entries.sort(key=lambda x: x[1])

        for i, (did, ts) in enumerate(entries):
            window_end = ts + timedelta(hours=TIMING_WINDOW_HOURS)
            in_window = [(d, t) for d, t in entries[i:] if t <= window_end]
            if len(in_window) >= TIMING_CLUSTER_MIN_COUNT:
                span_seconds = (in_window[-1][1] - in_window[0][1]).total_seconds()
                span_minutes = span_seconds / 60
                flags.append(AnomalyFlag(
                    decision_ids=[d for d, t in in_window],
                    detector="timing_anomaly",
                    statistical_basis={
                        "subject_id":           subject_id,
                        "decision_count":       len(in_window),
                        "window_hours":         TIMING_WINDOW_HOURS,
                        "actual_span_minutes":  round(span_minutes, 1),
                        "actual_span_seconds":  round(span_seconds, 1),
                        "first_decision_ts":    in_window[0][1].isoformat(),
                        "last_decision_ts":     in_window[-1][1].isoformat(),
                    },
                    description=(
                        f"Subject '{subject_id}' has {len(in_window)} decisions "
                        f"within {TIMING_WINDOW_HOURS}h "
                        f"(actual span: {span_minutes:.0f} min). "
                        f"Possible claim ring or duplicate submission."
                    ),
                ))
                reported_subjects.add(subject_id)
                break
    return flags


# ---------------------------------------------------------------------------
# Detector 4 — Near-duplicate detection (across full population)
# ---------------------------------------------------------------------------

def detect_near_duplicates(records: list) -> List[AnomalyFlag]:
    """
    Claims: buckets by (policy_id, claim_type, round(amount, -2)).
    Any bucket with 2+ decisions is a near-duplicate cluster.
    """
    flags = []
    claim_buckets: Dict[Tuple, List[str]] = defaultdict(list)

    for d, a in records:
        if _is_fixture(d.id):
            continue
        if d.function_type.value != "claims":
            continue
        snap = json.loads(a.inputs_snapshot)
        claim_data = snap.get("claim", {})
        policy_id  = claim_data.get("policy_id")
        claim_type = claim_data.get("claim_type")
        amount     = claim_data.get("amount")
        if not (policy_id and claim_type and amount is not None):
            continue
        # Round to nearest $100 bucket
        bucket_key = (policy_id, str(claim_type), int(round(float(amount), -2)))
        claim_buckets[bucket_key].append(d.id)

    for (policy_id, claim_type, bucket_amount), ids in claim_buckets.items():
        if len(ids) >= 2:
            flags.append(AnomalyFlag(
                decision_ids=ids,
                detector="near_duplicate",
                statistical_basis={
                    "similarity_basis":   "policy_id + claim_type + amount_rounded_to_100",
                    "policy_id":          policy_id,
                    "claim_type":         claim_type,
                    "amount_bucket":      f"~${bucket_amount:,}",
                    "decision_count":     len(ids),
                },
                description=(
                    f"{len(ids)} claims share policy_id='{policy_id}', "
                    f"claim_type='{claim_type}', amount≈${bucket_amount:,}. "
                    f"Near-duplicate pattern across population."
                ),
            ))
    return flags


# ---------------------------------------------------------------------------
# Detector 5 — Approval-rate anomaly (rolling window vs. historical baseline)
# ---------------------------------------------------------------------------

def detect_approval_rate_anomaly(records: list) -> List[AnomalyFlag]:
    """
    Splits each pipeline's decisions (chronologically) into historical and recent halves.
    Flags if the recent approval rate deviates by > APPROVAL_ANOMALY_Z_THRESHOLD
    standard deviations from the historical rate.

    Suppressed when total decisions < 10.
    """
    flags = []

    for pipeline in ["claims", "underwriting", "brokerage"]:
        pipeline_recs = sorted(
            [(d, a) for d, a in records
             if d.function_type.value == pipeline and not _is_fixture(d.id)],
            key=lambda x: x[0].timestamp,
        )
        if len(pipeline_recs) < 10:
            continue

        def _approved(d) -> int:
            return 1 if d.outcome in ("approve", "refer", "recommendation") else 0

        outcomes = [_approved(d) for d, _ in pipeline_recs]
        split = max(5, len(outcomes) // 2)
        historical = np.array(outcomes[:split], dtype=float)
        recent     = np.array(outcomes[split:], dtype=float)

        if len(historical) < 5 or len(recent) < 5:
            continue

        hist_rate  = float(np.mean(historical))
        hist_std   = float(np.std(historical, ddof=1))
        recent_rate = float(np.mean(recent))

        if hist_std < 1e-9:
            continue

        z = abs(recent_rate - hist_rate) / hist_std
        if z > APPROVAL_ANOMALY_Z_THRESHOLD:
            recent_ids = [d.id for d, _ in pipeline_recs[split:]]
            flags.append(AnomalyFlag(
                decision_ids=recent_ids,
                detector="approval_rate_anomaly",
                statistical_basis={
                    "pipeline":          pipeline,
                    "historical_rate":   round(hist_rate, 4),
                    "recent_rate":       round(recent_rate, 4),
                    "historical_std":    round(hist_std, 4),
                    "z_score":           round(z, 4),
                    "historical_n":      int(len(historical)),
                    "recent_n":          int(len(recent)),
                },
                description=(
                    f"{pipeline} recent approval rate {recent_rate:.1%} deviates "
                    f"{z:.2f}σ from historical baseline {hist_rate:.1%} "
                    f"(hist n={len(historical)}, recent n={len(recent)})."
                ),
            ))
    return flags


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def find_anomalies() -> List[AnomalyFlag]:
    """
    Runs all five detectors against the full decision population.
    Returns the union of all flags, excluding test fixtures.
    """
    with SessionLocal() as db:
        records = (
            db.query(DecisionRecord, AuditTrailRecord)
            .join(AuditTrailRecord, DecisionRecord.id == AuditTrailRecord.decision_id)
            .all()
        )

    all_flags: List[AnomalyFlag] = []
    for detector_fn in [
        detect_amount_outliers,
        detect_threshold_clustering,
        detect_timing_anomalies,
        detect_near_duplicates,
        detect_approval_rate_anomaly,
    ]:
        all_flags.extend(detector_fn(records))

    return all_flags
