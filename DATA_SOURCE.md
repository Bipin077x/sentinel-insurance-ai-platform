# DATA_SOURCE.md

## Dataset Information
- **Dataset Name**: Kaggle "Insurance Claim Fraud Detection" (`insurance_claims.csv`)
- **Origin**: Kaggle (uploaded by supen78, publicly hosted and redistributed in various repositories, e.g., mwitiderrick/insurancedata)
- **License/Terms**: Publicly available, typically CC0 / open data on Kaggle.
- **Privacy Assurance**: The dataset is completely synthetic or fully anonymized. It contains no real identifiable individuals despite modeling real US auto-insurance claim fraud patterns. It is widely used in fraud detection research.

## Purpose in Phase 12
This dataset replaces the hand-authored synthetic JSON fixtures for the Claims pipeline. It provides a real-world "messy" distribution with a genuine class imbalance (around 25% fraud rate) to test the robustness of the deterministic rules, anomaly detection (z-scores/IQR), and LLM calibration. Note that since this dataset is tabular, it bypasses the free-text extraction phase (`ingestion.py` / `intake.py` LLM stage), which remains validated only against the prior synthetic document tests.
