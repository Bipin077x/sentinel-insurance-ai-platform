"""
audit/generate_audit_findings.py — Markdown audit findings report.

Saved via reporting/utils.save_and_log_report so its SHA-256 hash is logged
to the DB. Same non-repudiation standard as the Phase 8 per-decision reports.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

from reporting.utils import save_and_log_report
from audit.anomaly_detection import AnomalyFlag
from audit.llm_review import AuditFinding


def generate_audit_findings(
    total_scanned:  int,
    results:        List[Dict[str, Any]],   # [{flag, finding, prompt_hash, confidence, faithfulness_errors}]
    audit_decision_ids: List[str],           # IDs of the logged audit Decision records
) -> str:
    """
    Renders a markdown audit findings report and saves it to disk.
    Returns the saved file path.

    Each result dict has:
      flag:               AnomalyFlag
      finding:            AuditFinding
      prompt_hash:        str
      calibrated_confidence: float
      faithfulness_errors: List[str]
    """
    now = datetime.now(timezone.utc)
    ts_label = now.strftime("%Y%m%d_%H%M%S")
    filename = f"audit_findings_{ts_label}.md"

    flagged = len(results)
    escalate_count        = sum(1 for r in results if r["finding"].recommended_action == "escalate")
    dismiss_count         = sum(1 for r in results if r["finding"].recommended_action == "dismiss_benign")
    senior_review_count   = sum(1 for r in results if r["finding"].recommended_action == "needs_senior_review")
    faithfulness_fail_count = sum(1 for r in results if r["faithfulness_errors"])

    # Detector breakdown
    detector_counts: Dict[str, int] = {}
    for r in results:
        det = r["flag"].detector
        detector_counts[det] = detector_counts.get(det, 0) + 1

    md = f"# Audit Findings Report\n\n"
    md += f"**Generated At:** {now.isoformat()}\n"
    md += f"**Records Scanned:** {total_scanned}\n"
    md += f"**Anomaly Flags Raised:** {flagged}\n"
    md += f"**Logged Audit Decision IDs:** {', '.join(f'`{i}`' for i in audit_decision_ids)}\n\n"

    md += "---\n\n## 1. Summary\n\n"
    md += f"| Category | Count |\n|---|---|\n"
    md += f"| Escalate — requires immediate human review | **{escalate_count}** |\n"
    md += f"| Needs senior review | **{senior_review_count}** |\n"
    md += f"| Dismissed as benign | **{dismiss_count}** |\n"
    md += f"| Faithfulness failures in audit findings | **{faithfulness_fail_count}** |\n\n"

    if faithfulness_fail_count:
        md += (
            "> [!CAUTION]\n"
            "> One or more audit findings had `cited_evidence` items that could not be verified "
            "> against the decision's inputs_snapshot or rule_results. These are marked below. "
            "> Fabricated citations in an audit finding undermine the finding's evidentiary basis.\n\n"
        )

    md += "## 2. Flags by Detector\n\n"
    for det, count in sorted(detector_counts.items()):
        md += f"- **{det}:** {count}\n"
    md += "\n---\n\n## 3. Individual Findings\n\n"

    for i, r in enumerate(results, 1):
        flag:    AnomalyFlag  = r["flag"]
        finding: AuditFinding = r["finding"]
        confidence            = r["calibrated_confidence"]
        f_errors              = r["faithfulness_errors"]

        action_label = {
            "escalate":           "🔴 ESCALATE",
            "dismiss_benign":     "🟢 DISMISS (BENIGN)",
            "needs_senior_review":"🟡 NEEDS SENIOR REVIEW",
        }.get(finding.recommended_action, finding.recommended_action)

        md += f"### Finding {i}: `{flag.detector}`\n\n"
        md += f"**Decision(s) Involved:** {', '.join(f'`{d}`' for d in flag.decision_ids)}\n\n"
        md += f"**Statistical Basis:**\n```json\n"
        md += __import__('json').dumps(flag.statistical_basis, indent=2)
        md += "\n```\n\n"
        md += f"**Pattern Description:** {flag.description}\n\n"
        md += f"**LLM Contextual Assessment** (calibrated confidence: {confidence:.0%}):\n"
        md += f"> {finding.audit_rationale}\n\n"
        md += f"**Cited Evidence:** {', '.join(f'`{e}`' for e in finding.cited_evidence)}\n\n"

        if f_errors:
            md += "**⚠ Faithfulness Failures:**\n"
            for err in f_errors:
                md += f"- {err}\n"
            md += "\n"

        if confidence < 0.6:
            md += (
                f"> [!WARNING]\n"
                f"> Calibrated agreement was {confidence:.0%} across samples. "
                f"This finding should not be relied upon without independent senior review.\n\n"
            )

        md += f"**Recommended Action:** {action_label}\n\n"
        md += f"**Prompt Hash:** `{r['prompt_hash']}`\n\n---\n\n"

    if not results:
        md += "_No anomalies detected in the current population._\n\n"

    file_path = save_and_log_report(
        report_content=md,
        report_type="audit_findings",
        filters={"total_scanned": total_scanned},
        filename=filename,
    )
    return file_path
