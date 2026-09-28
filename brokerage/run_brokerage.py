import json
import hashlib
from datetime import datetime, timezone
from brokerage.catalog import get_catalog
from brokerage.intake import process_intake
from brokerage.extraction import extract_client_needs, ExtractionValidationError
from brokerage.eligibility_filter import filter_eligible_products
from brokerage.recommendation import generate_recommendation
from core.calibration import compute_semantic_entropy
from core.models import Decision, AuditTrailEntry, FunctionType, DecisionStatus
from core.reasoning_log import log_decision
from core.validators import validate_client_needs
from core.redaction import redact_snapshot
from core.faithfulness import verify_faithfulness
from core.compliance import init_compliance, get_active_compliance_ruleset_hash
from core.model_registry import get_active_model, check_and_log_model_version
from core.database import init_db

def run_pipeline():
    init_db()
    check_and_log_model_version()
    init_compliance() # MUST fail immediately if manifest is mismatched
    
    active_model_id = get_active_model()
    catalog = get_catalog()
    
    with open("synthetic_clients.json", "r") as f:
        raw_clients = json.load(f)
        
    for client in raw_clients:
        print(f"Processing {client['client_id']}...")
        
        # 1. Intake
        document = process_intake(client)
        
        # 2. Extraction & Validation
        try:
            needs, prompt_hash_ext = extract_client_needs(document)
        except ExtractionValidationError as e:
            print(f"  -> Validation Failed (Fail Closed): {e.errors}")
            active_comp_hash = get_active_compliance_ruleset_hash()
            
            decision = Decision(
                id=f"dec_{client['client_id']}",
                function_type=FunctionType.EXTRACTION_VALIDATION,
                subject_id=client['client_id'],
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
                "raw_client": client,
                "extracted_needs": None
            }
            inputs_snapshot = redact_snapshot(inputs_snapshot_raw)
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
            
            log_decision(decision, audit_trail, raw_unredacted_text=document.raw_text)
            continue
            
        # 3. Rules (Eligibility Filter)
        eligible_products, excluded_products = filter_eligible_products(needs, catalog)
        
        # 4. Recommendation (Calibrated)
        def _brokerage_llm_caller():
            return generate_recommendation(needs, eligible_products)
            
        rec_out, prompt_hash_dec, calibrated_confidence, confidence_source = compute_semantic_entropy(_brokerage_llm_caller, num_samples=5)
        
        # 5. Semantic Labeling (Advisory, not a Gate)
        confidence_label = "High Confidence" if calibrated_confidence >= 0.85 else "Multiple Reasonable Options"
        
        # 6. Reasoning Log
        active_comp_hash = get_active_compliance_ruleset_hash()

        decision = Decision(
            id=f"dec_{client['client_id']}",
            function_type=FunctionType.BROKERAGE,
            subject_id=client['client_id'],
            outcome=f"recommendation",
            confidence_score=calibrated_confidence,
            confidence_source=confidence_source,
            rules_fired=[rec_out.recommended_product_id], # The chosen product
            reasoning_text=rec_out.reasoning_text,
            model_version=active_model_id,
            timestamp=datetime.now(timezone.utc),
            status=DecisionStatus.AUTO_DECIDED, # Brokerage is always auto-decided, it's advisory
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash_dec
        )
        
        # Faithfulness check
        actual_products_evaluated = [p.product_id for p in eligible_products]
        extracted_data_keys = list(needs.model_dump().keys())
        fabrication_errors = verify_faithfulness(
            rec_out.cited_products, 
            rec_out.cited_client_facts, 
            actual_products_evaluated, 
            extracted_data_keys,
            outcome=rec_out.recommended_product_id,
            reasoning_text=rec_out.reasoning_text
        )
        
        if fabrication_errors:
            decision.outcome = "fabrication_detected"
            decision.reasoning_text += f"\n[SYSTEM FLAG - FABRICATION DETECTED]: {'; '.join(fabrication_errors)}"
        
        inputs_snapshot_raw = {
            "client_needs": needs.model_dump(mode='json'),
            "eligible_catalog": [p.model_dump(mode='json') for p in eligible_products],
            "excluded_catalog": excluded_products,
            "llm_self_reported_confidence": rec_out.confidence,
            "consistency_label": confidence_label
        }
        inputs_snapshot = redact_snapshot(inputs_snapshot_raw)
        inputs_hash = hashlib.sha256(json.dumps(inputs_snapshot, sort_keys=True).encode()).hexdigest()
        
        audit_trail = AuditTrailEntry(
            decision_id=decision.id,
            inputs_hash=inputs_hash,
            inputs_snapshot=inputs_snapshot,
            rule_results={"excluded": excluded_products, "recommended": rec_out.recommended_product_id},
            model_prompt_version="v1",
            compliance_ruleset_hash=active_comp_hash,
            prompt_hash=prompt_hash_dec,
            reviewer_id=None,
            override_reason=None
        )
        
        log_decision(decision, audit_trail, raw_unredacted_text=document.raw_text)
        print(f"  -> Excluded: {excluded_products}")
        print(f"  -> Recommended: {rec_out.recommended_product_id}")
        print(f"  -> Confidence Label: {confidence_label} ({calibrated_confidence:.2f})")
        print(f"  -> Reasoning: {decision.reasoning_text}\n")
        
    print("Done generating recommendations. Run eval_brokerage.py for accuracy metrics.")

if __name__ == "__main__":
    run_pipeline()
