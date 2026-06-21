import os
import fitz
import pytesseract
from PIL import Image
import io
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import logging

logger = logging.getLogger(__name__)

# ✅ Make Tesseract path configurable via environment variable
TESSERACT_PATH = os.getenv('TESSERACT_PATH', 'tesseract')
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def get_page_text(doc, page_num, pdf_path):
    """Extract text from a page with OCR fallback."""
    page = doc[page_num]
    text = page.get_text()
    if text.strip():
        return text

    # Fallback OCR
    try:
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        ocr_text = pytesseract.image_to_string(img)
        return ocr_text
    except Exception as e:
        logger.warning(f"OCR failed for page {page_num+1}: {e}")
        return ""


def extract_text_from_pdf(pdf_path):
    """Extract full text from PDF (legacy, kept for compatibility)."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num in range(doc.page_count):
        full_text += get_page_text(doc, page_num, pdf_path) + "\n"
    doc.close()
    return full_text


def get_overall_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words=None)  # Could add stop_words='english'
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


def extract_pdf_structure(pdf_path):
    """
    Extract full text, table of contents, and chapters.
    Optimized: extracts page texts once and reuses them.
    """
    doc = fitz.open(pdf_path)
    page_count = doc.page_count

    # Extract all page texts once
    page_texts = []
    for pnum in range(page_count):
        page_texts.append(get_page_text(doc, pnum, pdf_path))

    full_text = "\n".join(page_texts)

    # Table of Contents
    toc = doc.get_toc()
    index = {"toc": [{"level": lvl, "title": title, "page": page} for lvl, title, page in toc]}

    # Chapters
    chapters = []
    if toc:
        toc_sorted = sorted(toc, key=lambda x: x[2])  # sort by page
        for i, (level, title, page) in enumerate(toc_sorted):
            start_page = page - 1
            end_page = (toc_sorted[i+1][2] - 1) if i+1 < len(toc_sorted) else page_count - 1
            # Collect text from page_texts
            chapter_text = "\n".join(page_texts[start_page:end_page+1])
            chapters.append({
                "title": title,
                "start_page": page,
                "end_page": end_page + 1 if i+1 < len(toc_sorted) else page_count,
                "text": chapter_text
            })
    else:
        chapters.append({
            "title": "Full Document",
            "start_page": 1,
            "end_page": page_count,
            "text": full_text
        })

    doc.close()
    return full_text, index, chapters