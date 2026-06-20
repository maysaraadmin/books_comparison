import fitz
import pytesseract
from pdf2image import convert_from_path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import os

# If Tesseract is not in PATH, set its location here (adjust for your system)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF. If no text is found, fall back to OCR.
    """
    # First, try PyMuPDF
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    if text.strip():
        return text

    # No text found – use OCR
    print(f"Extracting text via OCR for: {pdf_path}")
    try:
        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=300)
        ocr_text = ""
        for img in images:
            # Use Tesseract to extract text
            page_text = pytesseract.image_to_string(img)
            ocr_text += page_text + "\n"
        return ocr_text
    except Exception as e:
        print(f"OCR failed: {e}")
        return ""  # return empty if OCR fails

def get_overall_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words=None)
    try:
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        vectors = tfidf_matrix.toarray()
        return cosine_similarity([vectors[0]], [vectors[1]])[0][0]
    except ValueError:
        return 0.0

def get_line_differences(text1, text2):
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    diff = difflib.unified_diff(lines1, lines2, lineterm='')
    return '\n'.join(diff)