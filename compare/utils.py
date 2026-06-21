import os
import platform
import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import logging
import subprocess

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Tesseract path detection
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Check available languages
# ------------------------------------------------------------
def get_available_languages():
    try:
        output = subprocess.check_output([pytesseract.pytesseract.tesseract_cmd, '--list-langs'],
                                         stderr=subprocess.STDOUT,
                                         text=True)
        lines = output.splitlines()
        langs = [line.strip() for line in lines[1:] if line.strip()]
        return langs
    except Exception as e:
        logger.warning(f"Could not list Tesseract languages: {e}")
        return []

AVAILABLE_LANGS = get_available_languages()
logger.info(f"Tesseract available languages: {AVAILABLE_LANGS}")

if 'ara' in AVAILABLE_LANGS:
    OCR_LANG = 'ara+eng'
    logger.info("Using Arabic+English OCR")
else:
    OCR_LANG = 'eng'
    logger.warning("Arabic language not installed. Using English only.")

# ------------------------------------------------------------
# Image preprocessing
# ------------------------------------------------------------
def preprocess_image(img):
    if img.mode != 'L':
        img = img.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageOps.autocontrast(img, cutoff=2)
    return img

# ------------------------------------------------------------
# Page text extraction
# ------------------------------------------------------------
def get_page_text(doc, page_num):
    page = doc[page_num]
    text = page.get_text()
    if text.strip():
        return text

    try:
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        img = preprocess_image(img)
        config = '--psm 6'
        ocr_text = pytesseract.image_to_string(img, lang=OCR_LANG, config=config)
        return ocr_text
    except Exception as e:
        logger.warning(f"OCR failed for page {page_num+1}: {e}")
        return ""

# ------------------------------------------------------------
# PDF extraction with progress
# ------------------------------------------------------------
def extract_pdf_with_progress(pdf_path, progress_callback):
    doc = fitz.open(pdf_path)
    page_count = doc.page_count
    page_texts = []

    for pnum in range(page_count):
        text = get_page_text(doc, pnum)
        page_texts.append(text)
        if progress_callback:
            progress_callback(pnum + 1, page_count)

    full_text = "\n".join(page_texts)

    toc = doc.get_toc()
    index = {"toc": [{"level": lvl, "title": title, "page": page} for lvl, title, page in toc]}

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

# ------------------------------------------------------------
# Build marked text for diff
# ------------------------------------------------------------
def build_marked_text(full_text, chapters):
    if not chapters:
        return full_text
    marked_parts = []
    for ch in chapters:
        title = ch.get('title', 'Untitled')
        start = ch.get('start_page', '?')
        end = ch.get('end_page', '?')
        text = ch.get('text', '')
        marker = f"=== Chapter: {title} (pages {start}–{end}) ===\n"
        marked_parts.append(marker + text)
    return "\n\n".join(marked_parts)

# ------------------------------------------------------------
# TOC to text (for 'toc' mode)
# ------------------------------------------------------------
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

# ------------------------------------------------------------
# Similarity and diff
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

def get_line_differences(text1, text2, fromfile='First Book', tofile='Second Book'):
    lines1 = text1.splitlines()
    lines2 = text2.splitlines()
    diff = difflib.unified_diff(lines1, lines2, fromfile=fromfile, tofile=tofile, lineterm='')
    return '\n'.join(diff)

# ------------------------------------------------------------
# NEW: Compare TOC titles structurally
# ------------------------------------------------------------
def compare_toc_titles(toc1, toc2):
    """
    Compare two TOC lists (list of dicts with 'title' and 'page').
    Returns dict with:
      - common: list of {'title': str, 'page1': int, 'page2': int}
      - only1: list of {'title': str, 'page': int}
      - only2: list of {'title': str, 'page': int}
    """
    # Normalize titles (strip whitespace) for matching
    def normalize(title):
        return title.strip()

    # Build dicts mapping title -> page for each
    dict1 = {normalize(entry['title']): entry['page'] for entry in toc1}
    dict2 = {normalize(entry['title']): entry['page'] for entry in toc2}

    titles1 = set(dict1.keys())
    titles2 = set(dict2.keys())

    common_titles = titles1 & titles2
    only1_titles = titles1 - titles2
    only2_titles = titles2 - titles1

    common = [{'title': t, 'page1': dict1[t], 'page2': dict2[t]} for t in common_titles]
    only1 = [{'title': t, 'page': dict1[t]} for t in only1_titles]
    only2 = [{'title': t, 'page': dict2[t]} for t in only2_titles]

    # Sort by title (Arabic sorting may not be perfect but acceptable)
    common.sort(key=lambda x: x['title'])
    only1.sort(key=lambda x: x['title'])
    only2.sort(key=lambda x: x['title'])

    return {
        'common': common,
        'only1': only1,
        'only2': only2,
    }