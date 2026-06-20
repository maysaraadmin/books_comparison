import os
from django.shortcuts import render
from django.conf import settings
from .forms import PDFUploadForm
from .models import PDFDocument
from .utils import extract_text_from_pdf, get_overall_similarity, get_line_differences

def upload_and_compare(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save both uploaded files
            doc1 = PDFDocument.objects.create(file=request.FILES['doc1'])
            doc2 = PDFDocument.objects.create(file=request.FILES['doc2'])

            # Full paths to the saved files
            path1 = os.path.join(settings.MEDIA_ROOT, doc1.file.name)
            path2 = os.path.join(settings.MEDIA_ROOT, doc2.file.name)

            # Extract text
            text1 = extract_text_from_pdf(path1)
            text2 = extract_text_from_pdf(path2)

            # Check for empty text (scanned PDFs)
            if not text1.strip() or not text2.strip():
                context = {
                    'doc1_title': doc1.file.name,
                    'doc2_title': doc2.file.name,
                    'similarity': 0.0,
                    'diff_text': '⚠️ One or both PDFs contain no extractable text. They may be scanned images – consider using OCR.',
                }
                return render(request, 'compare/result.html', context)

            # Compute similarity and diff
            similarity = get_overall_similarity(text1, text2)
            diff_text = get_line_differences(text1, text2)

            context = {
                'doc1_title': doc1.file.name,
                'doc2_title': doc2.file.name,
                'similarity': round(similarity * 100, 2),
                'diff_text': diff_text,
            }
            return render(request, 'compare/result.html', context)
    else:
        form = PDFUploadForm()

    return render(request, 'compare/upload.html', {'form': form})