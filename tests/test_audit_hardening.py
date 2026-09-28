import pytest
import sqlite3
from core.database import SessionLocal, DecisionRecord, init_db, DATABASE_URL
from audit.chain_verify import verify_table_chain

# A helper to get a raw sqlite3 connection to bypass SQLAlchemy ORM safety
def get_raw_conn():
    # DATABASE_URL is "sqlite:///./insurance_platform.db"
    db_path = DATABASE_URL.replace("sqlite:///", "")
    return sqlite3.connect(db_path)

def test_triggers_block_update():
    """Test that the BEFORE UPDATE trigger prevents any modifications."""
    conn = get_raw_conn()
    cursor = conn.cursor()
    
    # Attempt to maliciously update a decision's outcome
    with pytest.raises(sqlite3.IntegrityError, match="UPDATE strictly forbidden"):
        cursor.execute("UPDATE decisions SET outcome = 'approve' WHERE id = 'dec_CLM-1001'")
        
    conn.close()

def test_triggers_block_delete():
    """Test that the BEFORE DELETE trigger prevents row deletion."""
    conn = get_raw_conn()
    cursor = conn.cursor()
    
    with pytest.raises(sqlite3.IntegrityError, match="DELETE strictly forbidden"):
        cursor.execute("DELETE FROM audit_trails WHERE decision_id = 'dec_CLM-1001'")
        
    conn.close()

def test_chain_verification_detects_tampering():
    """
    Test that if we somehow bypass the trigger (e.g. by dropping it, tampering, and recreating it),
    the chain verification will detect the broken hash.
    """
    # 1. First ensure the chain is currently valid
    with SessionLocal() as db:
        decisions = db.query(DecisionRecord).order_by(DecisionRecord.timestamp.asc()).all()
        assert verify_table_chain(DecisionRecord, decisions) == True
        
        if not decisions:
            pytest.skip("No data in DB to test tampering.")
            
        target_id = decisions[0].id
        
    # 2. Tamper with the row by dropping the trigger, updating, and recreating (simulating root DB access)
    conn = get_raw_conn()
    cursor = conn.cursor()
    
    cursor.execute("DROP TRIGGER block_decisions_update")
    cursor.execute("UPDATE decisions SET confidence_score = 0.99 WHERE id = ?", (target_id,))
    conn.commit()
    
    cursor.execute('''
        CREATE TRIGGER block_decisions_update BEFORE UPDATE ON decisions
        BEGIN SELECT RAISE(ABORT, 'UPDATE strictly forbidden on append-only table decisions'); END;
    ''')
    conn.commit()
    conn.close()
    
    # 3. Verify the chain now detects the tampering
    with SessionLocal() as db:
        decisions = db.query(DecisionRecord).order_by(DecisionRecord.timestamp.asc()).all()
        assert verify_table_chain(DecisionRecord, decisions) == False
