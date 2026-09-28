import json
import hashlib
import argparse
from datetime import datetime, timezone
from claims.intake import process_intake
from claims.extraction import extract_claim_info, ExtractionValidationError
from claims.rules import check_rules
from claims.fraud_flags import evaluate_fraud_flags
from claims.decision import make_decision
from core.calibration import compute_semantic_entropy
from core.gate import should_auto_decide
from core.database import SessionLocal
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision
from core.redaction import redact_snapshot
from core.faithfulness import verify_faithfulness
from core.compliance import init_compliance
from core.model_registry import get_active_model, check_and_log_model_version

from core.database import init_db
from integrations.mock_adapters import HttpClaimsAdapter, HttpPaymentAdapter

def run_pipeline(use_adapters: bool = False):
    init_db()
    check_and_log_model_version()
    init_compliance() # MUST fail immediately if manifest is mismatched
    
    active_model_id = get_active_model()
    
    claims_adapter = HttpClaimsAdapter() if use_adapters else None
    payment_adapter = HttpPaymentAdapter() if use_adapters else None
    
    with open("synthetic_claims.json", "r") as f:
        raw_claims = json.load(f)
        
    escalation_policy = {
        "claims": {
            "default_confidence_threshold": 0.85,
            "override_threshold": 0.5,
            "hard_ceiling": 1_000_000,  # Gate-layer hard stop. Distinct from the
                                         # extraction-layer sanity ceiling of $2M in validators.py.
            "stakes_thresholds": [
                {"max_stakes": 2000, "confidence_threshold": 0.85},
                {"max_stakes": None, "confidence_threshold": 0.95}
            ]
        }
    }
    
    for raw_claim in raw_claims:
        print(f"Processing {raw_claim['claim_id']}...")
        
        decision_id = f"dec_{raw_claim['claim_id']}"
        with SessionLocal() as db:
            from core.database import DecisionRecord
            if db.query(DecisionRecord).filter(DecisionRecord.id == decision_id).first():
                print(f"  [SKIP] Decision {decision_id} already exists.")
                continue

        if use_adapters:
            # We skip full document extraction in mock mode for simplicity and just get structured data
            claim = claims_adapter.fetch_claim(raw_claim["claim_id"])
            if not claim:
                print(f"  -> Failed to fetch {raw_claim['claim_id']} from adapter.")
                continue
            document = None
        else:
            # 1. Intake
            document = process_intake(raw_claim)
        
        # 2. Extraction & Validation (Validation is now internal to extraction.py)
        try:
            if use_adapters:
                prompt_hash_ext = "adapter_bypass"
            else:
                claim, prompt_hash_ext = extract_claim_info(document)
        except ExtractionValidationError as e:
            print(f"  -> Validation Failed (Fail Closed): {e.errors}")
            from core.compliance import get_active_compliance_ruleset_hash
            active_comp_hash = get_active_compliance_ruleset_hash()
            
            decision = Decision(
                id=f"dec_{raw_claim['claim_id']}",
                function_type=FunctionType.EXTRACTION_VALIDATION,
                subject_id=raw_claim['claim_id'],
                outcome="extraction_failed",
                confidence_score=1.0,
                confidence_source="deterministic",
                rules_fired=e.errors,
                reasoning_text=f"Extraction hallucination/sanity failure: {', '.join(e.errors)}",
                model_version=active_model_id,
                timestamp=datetime.now(timezone.utc),
                status=DecisionStatus.PENDING_REVIEW,
                compliance_ruleset_hash=active_comp_hash,
                prompt_hash=e.prompt_hash
            )
            
            # The snapshot should log the raw document in redacted form, and an empty claim
            inputs_snapshot_raw = {
                "raw_document": document.model_dump(mode='json'),
                "extracted_claim": None
            }
            # The intake step already redacted the raw document text! So we can just snapshot it.
            inputs_snapshot = inputs_snapshot_raw 
            inputs_hash = hashlib.sha256(json.dumps(inputs_snapshot, sort_keys=True).encode()).hexdigest()
            
            audit_trail = AuditTrailEntry(
                decision_id=decision.id,
                inputs_hash=inputs_hash,
                inputs_snapshot=inputs_snapshot,
                rule_results={"validation_passed": False},
                model_prompt_version="v1",
                compliance_ruleset_hash=active_comp_hash,
                prompt_hash=e.prompt_hash,
                reviewer_id=None,
                override_reason=None
            )
            
            log_decision(decision, audit_trail, raw_unredacted_text=raw_claim.get("raw_text", ""))
            continue
            
        # 3. Rules
        rule_results = check_rules(claim)
        
        # 4. Fraud Flags
        fraud_score, fraud_flags = evaluate_fraud_flags(claim)
        
        # 5. Decision (Calibrated)
        def _claims_llm_caller():
            return make_decision(claim, rule_results, fraud_score, fraud_flags)
            
        decision_out, prompt_hash_dec, calibrated_confidence, confidence_source = compute_semantic_entropy(_claims_llm_caller, num_samples=5)
        
        # 6. Gate (Escalation)
        can_auto_decide, auto_decide_reason = should_auto_decide(
            calibrated_confidence, 
            claim.amount, 
            "claims", 
            escalation_policy, 
            override_score=fraud_score,
            override_type="fraud",
            hard_ceiling=escalation_policy["claims"].get("hard_ceiling")
        )
        
        all_passed = all(r.passed for r in rule_results)
        
        # Gate requirements: 
        # "Auto-decide only if: all rules passed OR failed with high certainty, AND calibration.py agreement rate exceeds threshold, AND faithfulness check passed, AND amount is below the configured auto-decide ceiling"
        
        gate_passed = False
        reasoning_append = ""
        
        if not can_auto_decide:
            reasoning_append = f"Escalated: {auto_decide_reason}."
        else:
            if all_passed:
                gate_passed = True
            else:
                if calibrated_confidence >= 0.95:
                    gate_passed = True
                else:
                    reasoning_append = "Escalated: Rules failed but LLM confidence not high enough to auto-deny."
                    
        status = DecisionStatus.AUTO_DECIDED if gate_passed else DecisionStatus.PENDING_REVIEW
        
        # 6. Reasoning Log
        from core.compliance import get_active_compliance_ruleset_hash
        active_comp_hash = get_active_compliance_ruleset_hash()

        decision = Decision(
            id=f"dec_{claim.id}",
            function_type=FunctionType.CLAIMS,
            subject_id=claim.id,
            outcome=decision_out.outcome,
            confidence_score=calibrated_confidence,
            confidence_source=confidence_source,
            rules_fired=[r.rule_name for r in rule_results if not r.passed],
            reasoning_text=decision_out.reasoning_text,
            model_version=active_model_id,
            timestamp=datetime.now(timezone.utc),
            status=status,
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash_dec
        )
        
        # Faithfulness check
        actual_rules_fired = [r.rule_name for r in rule_results]
        extracted_data_keys = list(claim.model_dump().keys())
        fabrication_errors = verify_faithfulness(
            decision_out.cited_rules, 
            decision_out.cited_fields, 
            actual_rules_fired, 
            extracted_data_keys
        )
        
        if fabrication_errors:
            status = DecisionStatus.PENDING_REVIEW
            decision_out.outcome = "review" # Force review
            reasoning_append += f"\n[SYSTEM FLAG - FABRICATION DETECTED]: {'; '.join(fabrication_errors)}"
            
        decision.status = status
        decision.outcome = decision_out.outcome
        decision.reasoning_text += f"\n{reasoning_append}"
        
        # Build inputs snapshot
        inputs_snapshot = {
            "claim": claim.model_dump(mode='json'),
            "fraud_score": fraud_score,
            "fraud_flags": fraud_flags,
            "llm_self_reported_confidence": decision_out.confidence
        }
        # Already redacted during intake!
        inputs_hash = hashlib.sha256(json.dumps(inputs_snapshot, sort_keys=True).encode()).hexdigest()
        
        audit_trail = AuditTrailEntry(
            decision_id=decision.id,
            inputs_hash=inputs_hash,
            inputs_snapshot=inputs_snapshot,
            rule_results={r.rule_name: r.passed for r in rule_results},
            model_prompt_version="v1",
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash_dec,
            reviewer_id=None,
            # Store the structured gate reason so the escalation report reads a typed
            # field instead of pattern-matching free-text reasoning_text.
            override_reason=auto_decide_reason if not gate_passed else None
        )
        
        # Save raw, unredacted text into the secure store (from intake)
        log_decision(decision, audit_trail, raw_unredacted_text=raw_claim.get("raw_text", ""))
        print(f"  -> Outcome: {decision.outcome}, Status: {decision.status}, Reasoning: {decision.reasoning_text}\n")
        
        # Phase 6: Adapter push
        if use_adapters:
            claims_adapter.push_claim_decision(decision)
            if decision.outcome == "approve":
                payment_adapter.initiate_payout(decision.id, claim.amount, claim.policy_id)

def main():
    parser = argparse.ArgumentParser(description="Run the Claims Pipeline")
    parser.add_argument("--use-adapters", action="store_true", help="Use Phase 6 integration adapters")
    args = parser.parse_args()
    run_pipeline(use_adapters=args.use_adapters)

if __name__ == "__main__":
    main()
