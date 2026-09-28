"""
ingestion/document_parser.py — Mixed-format document ingestion (Phase 9)

Supports:
1. Native PDFs via pdfplumber
2. Scanned PDFs / Images via pytesseract

Normalizes output into a standard ParsedDocument model.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
    
    # Check if tesseract binary is actually available
    try:
        pytesseract.get_tesseract_version()
        TESSERACT_AVAILABLE = True
    except Exception:
        TESSERACT_AVAILABLE = False
except ImportError:
    pytesseract = None
    Image = None
    TESSERACT_AVAILABLE = False

@dataclass
class ParsedDocument:
    text: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    method: str = "unknown"

def parse_native_pdf(file_path: str) -> ParsedDocument:
    if not pdfplumber:
        raise ImportError("pdfplumber is required to parse native PDFs. 'pip install pdfplumber'")
    
    text_content = []
    tables = []
    
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)
            
            page_tables = page.extract_tables()
            for table in page_tables:
                if table:
                    tables.append({"data": table})
                    
    return ParsedDocument(
        text="\n".join(text_content),
        tables=tables,
        confidence=1.0,
        method="native_pdf"
    )

def parse_image_ocr(file_path: str) -> ParsedDocument:
    if not pytesseract or not Image:
        raise ImportError("pytesseract and pillow are required for OCR. 'pip install pytesseract pillow'")
    if not TESSERACT_AVAILABLE:
        raise ImportError(
            "Tesseract OCR binary is not available. Please install it on your system "
            "(e.g., from UB Mannheim on Windows) and ensure it's in your PATH."
        )
    
    img = Image.open(file_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    texts = []
    confidences = []
    
    for i, word in enumerate(data['text']):
        if word.strip():
            texts.append(word)
            confidences.append(float(data['conf'][i]))
            
    text = " ".join(texts)
    mean_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
    
    return ParsedDocument(
        text=text,
        tables=[],
        confidence=mean_conf,
        method="ocr"
    )

def parse_document(file_path: str, force_ocr: bool = False) -> ParsedDocument:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf' and not force_ocr:
        return parse_native_pdf(file_path)
    elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp'] or force_ocr:
        return parse_image_ocr(file_path)
    else:
        raise ValueError(f"Unsupported document format: {ext}")
