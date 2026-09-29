# Sentinel — AI-Native Insurance Platform (POC)

An evidence-native, AI-assisted platform for insurance brokerage, underwriting, claims processing, and financial audit — built as a proof of concept for ORIGIN-2026-PS01: AI-Powered Insurance and Finance Automation.

The core idea: separate what code should decide (rules, limits, exclusions) from what a language model should decide (judgment, ranking, synthesis), wrap every model call in checks designed for regulated finance, and make every decision reconstructable and independently verifiable — not just logged.

**Status:** proof of concept. Core architecture is built and adversarially tested. Several capabilities are explicitly unvalidated pending a live LLM, a real OCR install, real vendor API docs, and legal sign-off on two items. See [known_limitations.md](known_limitations.md) before assuming anything here is production-ready.

## What's actually built

| Function | What it does | Status |
| :--- | :--- | :--- |
| Brokerage | Extracts client needs, filters ineligible products deterministically, ranks the eligible set with an LLM, cites its reasoning | Built, adversarially tested |
| Underwriting | Applies eligibility rules + risk tier + deterministic referral-score override; accept / decline / refer | Built, tested; risk formula checked against real data (see below) |
| Claims | Validates against policy, computes a separate fraud score, decides approve / deny / review | Built, tested; fraud rule cross-validated on real data |
| Audit | Statistical anomaly detection over the decision population + LLM review of flagged cases | Statistical half real and tested; LLM discrimination half unvalidated (mock only) |

**Shared infrastructure underneath all four:**
- **Append-only, hash-chained ledger** (RFC 8785 canonical JSON + SHA-256 chain) — tamper-evident even if DB triggers are bypassed
- **Prompt & compliance-ruleset versioning** — hash-pinned, load fails loudly on drift
- **Faithfulness checking** — LLM-cited rules/fields must actually exist; outcome must match stated reasoning
- **Calibrated confidence** — self-consistency (5x resampling) instead of self-reported LLM confidence, plus deterministic overrides for "confidently wrong" cases
- **Escalation gate** — typed, logged reasons (fraud override, referral override, low confidence, amount ceiling)
- **Human review workflow** — overrides recorded as new append-only records, never edits
- **Retention & deletion job** — proven to hard-delete PII without breaking ledger chain integrity
- **Integration adapters** — realistic async/idempotent/partial-failure mechanics against a vendor-neutral mock contract
- **Reporting engine** — per-decision case audit reports + aggregate escalation/fairness/fabrication reports

## What's been validated against real (non-synthetic) data
- **Claims fraud detection:** tested on a public 1,000-record auto-insurance fraud dataset. A data-derived rule (incident_severity == "Major Damage") reached 60.6% precision / 42.5% recall under 5-fold cross-validation — independently rediscovered in every fold.
- **Underwriting risk stratification:** tested on a public 63,326-record travel-insurance dataset. Result: the existing synthetic risk formula does not meaningfully stratify real claim likelihood — a genuine, useful negative finding, root-caused to specific missing signal (trip duration) and one apparent signal (destination) that turned out to be a sales-agency confound, not real risk.
- **Fairness/proxy-bias harness:** built to test disparate impact from emergent correlation (not hand-coded bias). First version accidentally tested a hard threshold rather than genuine interaction effects — caught, reported honestly, and documented as a methodology finding in its own right.

## What is explicitly NOT validated
See [known_limitations.md](known_limitations.md) for the full, numbered list with required actions. Headline items:
- **No live LLM has been run.** Every pipeline above runs on a deterministic mock. Confidence calibration, fraud/anomaly semantic discrimination, and all escalation-rate numbers are mock artifacts, not production estimates.
- **OCR is unverified.** Native-PDF parsing works; the scanned-document path has only been exercised via its failure branch (Tesseract unavailable in the build environment).
- **No real vendor integration.** The adapter layer is realistic but generic — never tested against actual Guidewire/Duck Creek/etc. API docs.
- **No measured business outcomes.** Time and cost figures in any report are either mock-based structural placeholders or explicitly unmeasured — no fabricated human baseline exists anywhere in this project.
- **Two governance decisions are unresolved:** raw-document retention period (legal), and lawful demographic data sourcing for fairness testing (legal).

## Repository layout
- `core/` shared ledger, hashing, gate, calibration, redaction, registries
- `claims/` claims pipeline (intake, extraction, rules, fraud_flags, decision)
- `underwriting/` underwriting pipeline (+ referral_score, risk_scoring)
- `brokerage/` brokerage pipeline (+ eligibility_filter)
- `audit/` anomaly detection + LLM review + faithfulness on audit findings
- `reporting/` case audit reports, aggregate reports, deletion reports
- `review/` human review queue + CLI
- `integrations/` adapter interfaces, mock servers, realistic async/failure contract
- `fairness/` proxy-bias population generators + four-fifths evaluation
- `data/` real-data loaders (Kaggle claims, AXA travel), DATA_SOURCE notes
- `scratch/` adversarial test suites, per phase
- `docs/` known_limitations.md and phase reports

## Running it
```bash
pip install -r requirements.txt # or per-module as needed
python claims/run_claims.py # process synthetic claims batch
python underwriting/run_underwriting.py
python brokerage/run_brokerage.py
python audit/chain_verify.py # verify ledger integrity
python reporting/generate_case_audit.py <decision_id>
```

All of the above run against the mock LLM and synthetic/real-data fixtures already in the repo — no API key required. The staged real-LLM migration (`stage0_test.py` → `stage2_test.py`) requires a funded API key set locally in your own shell — never commit or paste a key into any file, prompt, or chat. See the Phase 14 section of the phase reports for the staged, cost-gated sequence.

## Design principles this project holds itself to
- **Deterministic first.** Anything checkable by code is checked by code, never left to model judgment.
- **Fail closed.** Invalid data, a failed integrity check, or an unavailable model routes to human review — never a silent default.
- **Evidence over assertion.** Every decision logs the exact prompt hash, ruleset hash, and model ID active at the time — not a self-reported summary of what happened.
- **"Done" is a claim to test, not a status to accept.** Every phase in this project's history was verified with pasted, adversarial output — real terminal results, negative cases included — not narrative summaries. This caught real bugs at nearly every phase (see docs/ phase reports) and, once, a fabricated execution claim from an AI coding assistant that was identified and voided before it entered the record.
- **Honest scope.** A capability is reported as verified, partially verified, or unverified — never rounded up.

## License / data sources
Public datasets used for validation (Kaggle auto-claims fraud set, AXA travel-insurance claims set) are documented with source and license in `data/DATA_SOURCE*.md`. No real client or policyholder data is used anywhere in this repository.
