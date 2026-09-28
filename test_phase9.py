import os
from ingestion.document_parser import parse_document
from ingestion.quality_gate import gate_document_quality

def test():
    docs = [
        "ingestion/test_documents/native_claim.pdf",
        "ingestion/test_documents/scanned_claim.png",
        "ingestion/test_documents/garbled_scan.png"
    ]
    
    for doc_path in docs:
        print(f"\nTesting {doc_path}...")
        try:
            parsed = parse_document(doc_path)
            print(f"Method: {parsed.method}, Confidence: {parsed.confidence:.2f}")
            print(f"Text snippet: {parsed.text[:50]!r}...")
            
            passed, reason = gate_document_quality(parsed)
            print(f"Gate passed: {passed}")
            if not passed:
                print(f"Reason: {reason}")
        except Exception as e:
            print(f"Error parsing: {e}")

if __name__ == "__main__":
    test()
