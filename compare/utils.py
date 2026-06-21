import os
import platform
import fitz
import pytesseract
from PIL import Image
import io
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import logging
import time

logger = logging.getLogger(__name__)

# Auto-detect Tesseract
if platform.system() == 'Windows':
    DEFAULT_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    DEFAULT_TESSERACT = 'tesseract'

TESSERACT_PATH = os.getenv('TESSERACT_PATH', DEFAULT_TESSERACT)
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    pytesseract.pytesseract.tesseract_cmd = 'tesseract'
    logger.warning(f"Tesseract not found at {TESSERACT_PATH}, falling back to PATH.")


def get_page_text(doc, page_num):
    """Extract text from a single page (without PDF path, not needed)."""
    page = doc[page_num]
    text = page.get_text()
    if text.strip():
        return text

    # OCR fallback
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


def extract_pdf_with_progress(pdf_path, progress_callback):
    """
    Extract full text, TOC, and chapters, reporting progress per page.
    progress_callback(current_page, total_pages)
    """
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    page_texts = []

    for pnum in range(page_count):
        text = get_page_text(doc, pnum)
        page_texts.append(text)
        # Report progress (1-based page number)
        if progress_callback:
            progress_callback(pnum + 1, page_count)

    full_text = "\n".join(page_texts)

    # Table of Contents
    toc = doc.get_toc()
    index = {"toc": [{"level": lvl, "title": title, "page": page} for lvl, title, page in toc]}

    # Chapters
    chapters = []
    if toc:
        toc_sorted = sorted(toc, key=lambda x: x[2])
        for i, (level, title, page) in enumerate(toc_sorted):
            start_page = page - 1
            end_page = (toc_sorted[i+1][2] - 1) if i+1 < len(toc_sorted) else page_count - 1
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


def toc_to_text(index_dict):
    toc = index_dict.get('toc', [])
    if not toc:
        return ""
    lines = []
    for entry in toc:
        level = entry.get('level', 0)
        title = entry.get('title', '')
        page = entry.get('page', 0)
        indent = "  " * (level - 1)
        lines.append(f"{indent}{title} (page {page})")
    return "\n".join(lines)


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