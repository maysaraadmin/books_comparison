import os
from django.shortcuts import render
from django.conf import settings
from .forms import PDFUploadForm
from .models import PDFDocument
from .utils import extract_pdf_structure, get_overall_similarity, get_line_differences

def upload_and_compare(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save both PDFs and extract structure
            doc1 = PDFDocument.objects.create(file=request.FILES['doc1'])
            doc2 = PDFDocument.objects.create(file=request.FILES['doc2'])

            path1 = os.path.join(settings.MEDIA_ROOT, doc1.file.name)
            path2 = os.path.join(settings.MEDIA_ROOT, doc2.file.name)

            # Extract structured data for doc1
            content1, index1, chapters1 = extract_pdf_structure(path1)
            doc1.content = content1
            doc1.index = index1
            doc1.chapters = chapters1
            doc1.save()

            # Extract for doc2
            content2, index2, chapters2 = extract_pdf_structure(path2)
            doc2.content = content2
            doc2.index = index2
            doc2.chapters = chapters2
            doc2.save()

            # Now compare (using full content)
            similarity = get_overall_similarity(content1, content2)
            diff_text = get_line_differences(content1, content2)

            context = {
                'doc1_title': doc1.file.name,
                'doc2_title': doc2.file.name,
                'similarity': round(similarity * 100, 2),
                'diff_text': diff_text,
                # Optionally pass chapter info for display
                'doc1_chapters': chapters1,
                'doc2_chapters': chapters2,
            }
            return render(request, 'compare/result.html', context)
    else:
        form = PDFUploadForm()
    return render(request, 'compare/upload.html', {'form': form})