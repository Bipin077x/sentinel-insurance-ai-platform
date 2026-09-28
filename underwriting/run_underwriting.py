import json
import hashlib
from datetime import datetime, timezone
from underwriting.intake import process_intake
from underwriting.extraction import extract_application_info
from underwriting.rules import check_rules
from underwriting.risk_scoring import evaluate_risk
from underwriting.decision import make_underwriting_decision
from underwriting.referral_score import evaluate_referral_score
from core.calibration import compute_semantic_entropy
from core.gate import should_auto_decide
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision
from underwriting.extraction import ExtractionValidationError
from core.validators import validate_application
from core.redaction import redact_snapshot
from core.faithfulness import verify_faithfulness
from core.compliance import init_compliance
from core.model_registry import get_active_model, check_and_log_model_version
from core.database import init_db
from integrations.mock_adapters import HttpPolicyAdminAdapter
import argparse

def run_pipeline(use_adapters: bool = False):
    init_db()
    check_and_log_model_version()
    init_compliance() # MUST fail immediately if manifest is mismatched
    
    active_model_id = get_active_model()
    
    policy_adapter = HttpPolicyAdminAdapter() if use_adapters else None
    
    with open("synthetic_applications.json", "r") as f:
        raw_apps = json.load(f)
        
    escalation_policy = {
        "underwriting": {
            "default_confidence_threshold": 0.90,
            "override_threshold": 0.8,
            "stakes_thresholds": [
                # In underwriting, stakes could be the trip cost
                {"max_stakes": 5000, "confidence_threshold": 0.85},
                {"max_stakes": None, "confidence_threshold": 0.95}
            ]
        }
    }
    
    for raw_app in raw_apps:
        print(f"Processing {raw_app['app_id']}...")
        
        if use_adapters:
            # We skip full document extraction in mock mode for simplicity and just get structured data
            # Simulate adapter fetch (since we don't have a fetch_application in PolicyAdminAdapter yet, 
            # we just construct it from raw_app for test purposes)
            from core.models import Application
            app = Application(**raw_app)
            document = None
            prompt_hash_ext = "adapter_bypass"
        else:
            # 1. Intake
            document = process_intake(raw_app)
            
            # 2. Extraction & Validation
            try:
                app, prompt_hash_ext = extract_application_info(document)
            except ExtractionValidationError as e:
                print(f"  -> Validation Failed (Fail Closed): {e.errors}")
                from core.compliance import get_active_compliance_ruleset_hash
                active_comp_hash = get_active_compliance_ruleset_hash()
                
                decision = Decision(
                    id=f"dec_{raw_app['app_id']}",
                    function_type=FunctionType.EXTRACTION_VALIDATION,
                    subject_id=raw_app['app_id'],
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
                
                inputs_snapshot_raw = {
                    "raw_document": document.model_dump(mode='json'),
                    "extracted_app": None
                }
                # Document is already redacted at intake
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
                
                # Save raw, unredacted text securely
                log_decision(decision, audit_trail, raw_unredacted_text=raw_app.get("raw_text", ""))
                continue
        # 3. Rules
        rule_results = check_rules(app)
        
        # 3.5 Referral Score Override Signal
        referral_score, referral_flags = evaluate_referral_score(app)
        
        # 4. Risk Scoring
        risk_tier, suggested_premium, narrative = evaluate_risk(app)
        
        # 4. Decision (Calibrated)
        def _underwriting_llm_caller():
            return make_underwriting_decision(app, rule_results, risk_tier, suggested_premium, narrative)
            
        decision_out, prompt_hash_dec, calibrated_confidence, confidence_source = compute_semantic_entropy(_underwriting_llm_caller, num_samples=5)
        
        # 5. Gate (Escalation)
        can_auto_decide, auto_decide_reason = should_auto_decide(
            calibrated_confidence, 
            app.trip_cost, 
            "underwriting", 
            escalation_policy, 
            override_score=referral_score,
            override_type="referral"
        )
        
        all_passed = all(r.passed for r in rule_results)
        gate_passed = False
        reasoning_append = ""
        
        if not can_auto_decide:
            # could be fraud_override or low_calibration_confidence
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
        
        if not gate_passed:
            decision_out.outcome = "refer" # Force referral state for non-auto cases
            
        decision_out.reasoning_text += f"\n{reasoning_append}"
        
        # 7. Reasoning Log
        from core.compliance import get_active_compliance_ruleset_hash
        active_comp_hash = get_active_compliance_ruleset_hash()

        decision = Decision(
            id=f"dec_{app.id}",
            function_type=FunctionType.UNDERWRITING,
            subject_id=app.id,
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
        extracted_data_keys = list(app.model_dump().keys())
        fabrication_errors = verify_faithfulness(
            decision_out.cited_rules, 
            decision_out.cited_fields, 
            actual_rules_fired, 
            extracted_data_keys
        )
        
        if fabrication_errors:
            decision.status = DecisionStatus.PENDING_REVIEW
            decision.outcome = "fabrication_detected"
            decision.reasoning_text += f"\n[SYSTEM FLAG - FABRICATION DETECTED]: {'; '.join(fabrication_errors)}"
        
        inputs_snapshot_raw = {
            "application": app.model_dump(mode='json'),
            "risk_assessment": {
                "tier": risk_tier,
                "suggested_premium": suggested_premium,
                "narrative": narrative
            },
            "referral_score": referral_score,
            "referral_flags": referral_flags,
            "llm_self_reported_confidence": decision_out.confidence
        }
        # Already redacted during intake!
        inputs_snapshot = inputs_snapshot_raw
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
        
        log_decision(decision, audit_trail, raw_unredacted_text=document.raw_text if document else raw_app.get("raw_text", ""))
        print(f"  -> Outcome: {decision.outcome}, Premium: ${decision_out.final_premium:.2f}, Status: {decision.status}, Reasoning: {decision.reasoning_text}\n")
        
        # Phase 6: Adapter push
        if use_adapters:
            policy_adapter.push_decision(decision)

def main():
    parser = argparse.ArgumentParser(description="Run the Underwriting Pipeline")
    parser.add_argument("--use-adapters", action="store_true", help="Use Phase 6 integration adapters")
    args = parser.parse_args()
    run_pipeline(use_adapters=args.use_adapters)

if __name__ == "__main__":
    main()
