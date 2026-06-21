import fitz
import pytesseract
from PIL import Image
import io
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib

# ------------------------------------------------------------
# Set Tesseract path (exactly where you installed it)
# ------------------------------------------------------------
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ------------------------------------------------------------
# Helper: get text from a single page (with OCR fallback)
# ------------------------------------------------------------
def get_page_text(doc, page_num, pdf_path):
    """
    Extract text from a specific page.
    First tries PyMuPDF; if empty, uses OCR via PyMuPDF → image → Tesseract.
    """
    page = doc[page_num]
    text = page.get_text()
    if text.strip():
        return text

    # Fallback to OCR – render page to image using PyMuPDF
    try:
        # Render at 300 DPI (scale factor: 300/72 ≈ 4.17)
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # Run Tesseract OCR
        ocr_text = pytesseract.image_to_string(img)
        return ocr_text
    except Exception as e:
        print(f"OCR failed for page {page_num+1}: {e}")
        return ""

# ------------------------------------------------------------
# Main text extraction (full document)
# ------------------------------------------------------------
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num in range(doc.page_count):
        full_text += get_page_text(doc, page_num, pdf_path) + "\n"
    doc.close()
    return full_text

# ------------------------------------------------------------
# Similarity and diff functions
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Advanced structure extraction (content, index, chapters)
# ------------------------------------------------------------
def extract_pdf_structure(pdf_path):
    doc = fitz.open(pdf_path)

    # Full text (using OCR-aware per-page extraction)
    full_text = ""
    for page_num in range(doc.page_count):
        full_text += get_page_text(doc, page_num, pdf_path) + "\n"

    # Table of Contents
    toc = doc.get_toc()
    index = {"toc": [{"level": lvl, "title": title, "page": page} for lvl, title, page in toc]}

    # Chapters
    chapters = []
    if toc:
        toc_sorted = sorted(toc, key=lambda x: x[2])
        for i, (level, title, page) in enumerate(toc_sorted):
            start_page = page - 1
            end_page = (toc_sorted[i+1][2] - 1) if i+1 < len(toc_sorted) else doc.page_count - 1
            chapter_text = ""
            for pnum in range(start_page, min(end_page + 1, doc.page_count)):
                chapter_text += get_page_text(doc, pnum, pdf_path) + "\n"
            chapters.append({
                "title": title,
                "start_page": page,
                "end_page": end_page + 1 if i+1 < len(toc_sorted) else doc.page_count,
                "text": chapter_text
            })
    else:
        chapters.append({
            "title": "Full Document",
            "start_page": 1,
            "end_page": doc.page_count,
            "text": full_text
        })

    doc.close()
    return full_text, index, chapters