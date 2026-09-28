# AI-Native Insurance Services Platform (POC)

This is a proof-of-concept for an AI-native insurance platform encompassing Claims, Underwriting, Brokerage, and Financial Audit functionalities. 

## Architectural Principles
1. **Separate Deterministic Logic**: Rules are plain code; LLMs synthesize outputs based on structured rule results.
2. **Structured Reasoning Trail**: Every decision logs an exhaustive hash-chained snapshot of inputs, outputs, and rule results.
3. **Confidence-Based Escalation**: LLM uncertainty drives human escalation.

## Evidentiary Integrity & WORM Storage

This platform has been hardened for regulatory audit (Phase 1.5):
- **Canonical Hashing**: All decisions and audit trails are serialized using RFC 8785 (JSON Canonicalization Scheme) to ensure that logical data always produces the identical SHA-256 hash across any system or language.
- **Append-Only Database**: `BEFORE UPDATE` and `BEFORE DELETE` triggers physically reject modifications to the SQLite ledger tables at the database level.
- **Hash Chaining**: Every record contains the `record_hash` of the previous record, generating a cryptographically sound sequence.

### Limitations & Production Requirements
While local SQLite triggers and hash chains prove the concept, they **do not provide true non-repudiation** against an actor with root database access. A malicious actor could drop the DB triggers, rewrite history, recalculate all sequential hashes from the tampering point forward, and recreate the triggers.

**To achieve true WORM (Write Once Read Many) guarantees in production:**
1. **Infrastructure WORM**: The database must be hosted on an infrastructure layer that physically rejects mutations (e.g., AWS QLDB, or writing logs to AWS S3 Object Lock).
2. **External Ledger Anchoring**: The tip of the hash chain must be periodically anchored (e.g., every 10 minutes) to an external, immutable timestamping authority or public blockchain. See `audit/external_anchor.py` for the stubbed interface.
