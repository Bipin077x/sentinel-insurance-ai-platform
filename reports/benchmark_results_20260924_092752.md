# Business Outcome Benchmarks

NOTE: All timing figures are for mock-LLM synthetic runs.
LLM call durations are near-zero (in-process function calls, not network calls).
These figures represent structural overhead only, NOT representative of production latency.
Human baseline: no verifiable baseline available. See known_limitations.md Item 3.

## Timing Results (Total over 33 decisions)

- **intake**: 0.3429s
- **extraction**: 0.6772s
- **rules**: 0.1799s
- **llm_decision**: 0.3454s
- **calibration_sampling**: 1.6630s
- **gate**: 0.0515s
- **log_decision**: 0.3456s

## Cost Estimation

*Note: Pricing is based on reference models. Verify against your provider.*

- Total Input Tokens: 32,990
- Total Output Tokens: 3,220
- Estimated Cost (Batch): $0.2133
- Projected Cost per 1,000 Decisions: $213.25

**Calibration Sampling Overhead**: The calibration process requested 5 samples, meaning the structural cost of LLM generation is multiplied by 5.
