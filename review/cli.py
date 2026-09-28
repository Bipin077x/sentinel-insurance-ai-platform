import sys
import uuid
import hashlib
import json
from datetime import datetime, timezone
from core.database import SessionLocal, ReviewRecord, DecisionRecord
from core.models import DecisionStatus
from review.queue import list_pending
from reporting.generate_case_audit import generate_case_audit

def main():
    print("Welcome to the Human Review CLI")
    while True:
        pending = list_pending()
        
        # Filter out those already reviewed (since we append ReviewRecord, the decision record itself isn't modified to reflect it)
        with SessionLocal() as db:
            reviewed_ids = {r.decision_id for r in db.query(ReviewRecord).all()}
        pending = [d for d in pending if d.id not in reviewed_ids]

        if not pending:
            print("No pending decisions to review.")
            break
            
        print(f"\n{len(pending)} decisions pending review:")
        for i, dec in enumerate(pending[:10]):
            print(f"[{i}] {dec.id} - {dec.outcome} (Confidence: {dec.confidence_score})")
            
        print("\nEnter a decision index to review, or 'q' to quit:")
        choice = input("> ").strip()
        
        if choice.lower() == 'q':
            break
            
        try:
            idx = int(choice)
            dec = pending[idx]
        except (ValueError, IndexError):
            print("Invalid selection.")
            continue
            
        print(f"\n--- Reviewing {dec.id} ---")
        report = generate_case_audit(dec.id)
        if report:
            print("Case audit report generated:")
            print(report[:1000] + "\n... (truncated for CLI view)")
        else:
            print("Could not generate case audit report (decision not found in DB).")
            
        print("\nAction: [A]pprove / [D]eny / [M]odify / [S]kip")
        action = input("> ").strip().upper()
        
        if action == 'S':
            continue
            
        if action not in ['A', 'D', 'M']:
            print("Invalid action.")
            continue
            
        action_map = {'A': 'approve', 'D': 'deny', 'M': 'modify'}
        action_str = action_map[action]
        
        reviewer_id = input("Reviewer ID: ").strip()
        if not reviewer_id:
            print("Reviewer ID required.")
            continue
            
        justification = input("Justification: ").strip()
        if not justification:
            print("Justification required.")
            continue
            
        final_outcome = dec.outcome
        if action == 'D':
            final_outcome = 'deny' if dec.outcome != 'deny' else dec.outcome
        elif action == 'M':
            final_outcome = input(f"Enter new outcome (original was {dec.outcome}): ").strip()
            
        now = datetime.now(timezone.utc)
        record_id = f"rev_{uuid.uuid4().hex[:8]}"
        
        # Calculate hash for ReviewRecord
        data_to_hash = {
            "id": record_id,
            "decision_id": dec.id,
            "reviewer_id": reviewer_id,
            "action": action_str,
            "original_outcome": dec.outcome,
            "final_outcome": final_outcome,
            "justification": justification,
            "timestamp": now.isoformat()
        }
        
        # In a real WORM we might chain this, but simple hash for now
        record_hash = hashlib.sha256(json.dumps(data_to_hash, sort_keys=True).encode()).hexdigest()
        
        review_record = ReviewRecord(
            id=record_id,
            decision_id=dec.id,
            reviewer_id=reviewer_id,
            action=action_str,
            original_outcome=dec.outcome,
            final_outcome=final_outcome,
            justification=justification,
            timestamp=now,
            record_hash=record_hash
        )
        
        with SessionLocal() as db:
            db.add(review_record)
            db.commit()
            
        print(f"Successfully recorded review. Record Hash: {record_hash}")

if __name__ == "__main__":
    main()
