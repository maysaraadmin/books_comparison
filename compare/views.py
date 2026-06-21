import os
import logging
from django.shortcuts import render
from django.conf import settings
from .forms import PDFUploadForm
from .models import PDFDocument
from .utils import extract_pdf_structure, get_overall_similarity, get_line_differences

logger = logging.getLogger(__name__)

def upload_and_compare(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc1 = None
            doc2 = None
            try:
                # Save both PDFs
                doc1 = PDFDocument.objects.create(file=request.FILES['doc1'])
                doc2 = PDFDocument.objects.create(file=request.FILES['doc2'])

                path1 = os.path.join(settings.MEDIA_ROOT, doc1.file.name)
                path2 = os.path.join(settings.MEDIA_ROOT, doc2.file.name)

                # Extract structured data
                content1, index1, chapters1 = extract_pdf_structure(path1)
                content2, index2, chapters2 = extract_pdf_structure(path2)

                doc1.content = content1
                doc1.index = index1
                doc1.chapters = chapters1
                doc1.save()

                doc2.content = content2
                doc2.index = index2
                doc2.chapters = chapters2
                doc2.save()

                # Compute similarity and diff
                similarity = get_overall_similarity(content1, content2)
                diff_text = get_line_differences(content1, content2)

                context = {
                    'doc1': doc1,
                    'doc2': doc2,
                    'similarity': round(similarity * 100, 2),
                    'diff_text': diff_text,
                }
                return render(request, 'compare/result.html', context)

            except Exception as e:
                logger.error(f"Error processing PDFs: {e}")
                # Delete incomplete records to avoid orphaned files
                if doc1:
                    doc1.delete()
                if doc2:
                    doc2.delete()
                # Re‑raise or show a friendly error page
                return render(request, 'compare/error.html', {'message': 'Failed to process one or both PDF files. Please ensure they are valid PDFs.'})
    else:
        form = PDFUploadForm()
    return render(request, 'compare/upload.html', {'form': form})