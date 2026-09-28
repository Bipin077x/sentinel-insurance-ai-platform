# Fairness Summary Report

**Pipeline:** underwriting
**Generated At:** 2026-09-23T09:04:35.120935+00:00

> [!CAUTION]
> **STRUCTURAL LIMITATIONS OF THIS REPORT**
>
> **This report must NOT be interpreted as validation that this system is fair.**
>
> 1. **Synthetic Demographic Data Only**: The data evaluated here is entirely synthetic. It does not represent a real population distribution and has not been sourced through legally validated inference methods (e.g., BISG). Results cannot be generalized to production use.
>
> 2. **Maximal Signal Testing Only**: This evaluation tests for extreme, direct, near-perfect correlations with protected attributes. It provides no evidence about subtle, real-world proxy correlations (e.g., zip code, employment sector, trip destination correlating with protected classes). A clean result here means only that egregious explicit bias was not detected — not that no disparate impact exists.
>
> **Regulatory Use**: This report is a development-stage POC artifact, not a regulatory compliance submission.

## 1. Fairness Evaluation Output
```text
--- Underwriting Fairness Evaluation (Synthetic POC) ---
WARNING: This evaluation runs against purely synthetic demographic attributes.
Production demographic sourcing (e.g., BISG inference) requires explicit legal and compliance sign-off.
--------------------------------------------------------

Approval Rates by Demographic Group:
  Group B: 2/14 (14.3%) | Referred: 4 | Declined: 8
  Group A: 6/11 (54.5%) | Referred: 5 | Declined: 0

Feature Correlation Check (Proxy Bias Detection):
  Feature: destination
    France -> Group B: 2/8 (25.0%) | Group A: 6/8 (75.0%) | 
    Italy -> Group B: 3/3 (100.0%) | 
    North Korea -> Group B: 3/3 (100.0%) | 
    Switzerland -> Group B: 2/6 (33.3%) | Group A: 4/6 (66.7%) | 
    USA -> Group B: 3/3 (100.0%) | 
    Canada -> Group A: 1/2 (50.0%) | Group B: 1/2 (50.0%) | 

Note: Disparate impact is considered a flag if the approval rate ratio between groups falls below 0.8 (four-fifths rule).

```

