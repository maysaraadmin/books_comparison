import os
import logging
import threading
import time
import uuid
from django.shortcuts import render, redirect
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from .forms import PDFUploadForm
from .models import PDFDocument
from .utils import (
    extract_pdf_with_progress,
    get_overall_similarity,
    get_line_differences,
    toc_to_text,
    build_marked_text,
    compare_toc_titles,
)

logger = logging.getLogger(__name__)


def upload_and_compare(request):
    if request.method == 'POST':
        form = PDFUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc1 = PDFDocument.objects.create(file=request.FILES['doc1'])
            doc2 = PDFDocument.objects.create(file=request.FILES['doc2'])

            import fitz
            path1 = os.path.join(settings.MEDIA_ROOT, doc1.file.name)
            path2 = os.path.join(settings.MEDIA_ROOT, doc2.file.name)
            with fitz.open(path1) as d1:
                pages1 = d1.page_count
            with fitz.open(path2) as d2:
                pages2 = d2.page_count

            job_id = str(uuid.uuid4())
            job_data = {
                'status': 'processing',
                'progress': 0,
                'total_pages': pages1 + pages2,
                'pages_done_doc1': 0,
                'pages_done_doc2': 0,
                'start_time': time.time(),
                'doc1_id': doc1.id,
                'doc2_id': doc2.id,
                'comparison_type': form.cleaned_data['comparison_type'],
                'doc1_pages': pages1,
                'doc2_pages': pages2,
                'doc1_name': doc1.file.name,
                'doc2_name': doc2.file.name,
            }
            cache.set(f'job_{job_id}', job_data, timeout=3600)

            thread = threading.Thread(target=process_comparison, args=(job_id,))
            thread.daemon = True
            thread.start()

            return redirect('compare:progress_page', job_id=job_id)
    else:
        form = PDFUploadForm()
    return render(request, 'compare/upload.html', {'form': form})


def process_comparison(job_id):
    job_data = cache.get(f'job_{job_id}')
    if not job_data:
        return

    doc1 = PDFDocument.objects.get(id=job_data['doc1_id'])
    doc2 = PDFDocument.objects.get(id=job_data['doc2_id'])
    path1 = os.path.join(settings.MEDIA_ROOT, doc1.file.name)
    path2 = os.path.join(settings.MEDIA_ROOT, doc2.file.name)

    def update_progress(current_page, total_pages, doc_index):
        job_data = cache.get(f'job_{job_id}')
        if not job_data:
            return
        if doc_index == 1:
            job_data['pages_done_doc1'] = current_page
        else:
            job_data['pages_done_doc2'] = current_page
        pages_done = job_data['pages_done_doc1'] + job_data['pages_done_doc2']
        total = job_data['total_pages']
        job_data['progress'] = int((pages_done / total) * 100) if total > 0 else 0
        cache.set(f'job_{job_id}', job_data, timeout=3600)

    try:
        content1, index1, chapters1 = extract_pdf_with_progress(
            path1,
            lambda p, t: update_progress(p, t, 1)
        )
        content2, index2, chapters2 = extract_pdf_with_progress(
            path2,
            lambda p, t: update_progress(p, t, 2)
        )

        doc1.content = content1
        doc1.index = index1
        doc1.chapters = chapters1
        doc1.save()

        doc2.content = content2
        doc2.index = index2
        doc2.chapters = chapters2
        doc2.save()

        comparison_type = job_data['comparison_type']

        # Default values
        similarity = 0
        diff_text = ''
        toc_comparison = None

        if comparison_type == 'full':
            text1, text2 = content1, content2
            similarity = get_overall_similarity(text1, text2)
            marked_text1 = build_marked_text(content1, chapters1)
            marked_text2 = build_marked_text(content2, chapters2)
            diff_text = get_line_differences(marked_text1, marked_text2,
                                             fromfile=doc1.file.name,
                                             tofile=doc2.file.name)

        elif comparison_type == 'toc':
            text1, text2 = toc_to_text(index1), toc_to_text(index2)
            similarity = get_overall_similarity(text1, text2)
            diff_text = get_line_differences(text1, text2,
                                             fromfile=doc1.file.name,
                                             tofile=doc2.file.name)

        elif comparison_type == 'chapters':
            text1 = "\n".join([ch['text'] for ch in chapters1])
            text2 = "\n".join([ch['text'] for ch in chapters2])
            similarity = get_overall_similarity(text1, text2)
            # Also build marked diff
            marked_text1 = build_marked_text(content1, chapters1)
            marked_text2 = build_marked_text(content2, chapters2)
            diff_text = get_line_differences(marked_text1, marked_text2,
                                             fromfile=doc1.file.name,
                                             tofile=doc2.file.name)

        elif comparison_type == 'toc_chapters':
            text1 = toc_to_text(index1) + "\n\n" + "\n".join([ch['text'] for ch in chapters1])
            text2 = toc_to_text(index2) + "\n\n" + "\n".join([ch['text'] for ch in chapters2])
            similarity = get_overall_similarity(text1, text2)
            marked_text1 = build_marked_text(content1, chapters1)
            marked_text2 = build_marked_text(content2, chapters2)
            diff_text = get_line_differences(marked_text1, marked_text2,
                                             fromfile=doc1.file.name,
                                             tofile=doc2.file.name)

        elif comparison_type == 'toc_titles':
            # NEW: Compare TOC titles only
            toc1 = index1.get('toc', [])
            toc2 = index2.get('toc', [])
            toc_comparison = compare_toc_titles(toc1, toc2)
            # No diff needed, similarity not meaningful
            similarity = 0
            diff_text = ''

        else:
            # fallback to full
            text1, text2 = content1, content2
            similarity = get_overall_similarity(text1, text2)
            marked_text1 = build_marked_text(content1, chapters1)
            marked_text2 = build_marked_text(content2, chapters2)
            diff_text = get_line_differences(marked_text1, marked_text2,
                                             fromfile=doc1.file.name,
                                             tofile=doc2.file.name)

        job_data['status'] = 'done'
        job_data['progress'] = 100
        job_data['similarity'] = round(similarity * 100, 2) if comparison_type != 'toc_titles' else None
        job_data['diff_text'] = diff_text
        job_data['total_time'] = time.time() - job_data['start_time']
        job_data['toc_comparison'] = toc_comparison  # store structured data
        cache.set(f'job_{job_id}', job_data, timeout=3600)

    except Exception as e:
        logger.error(f"Error in background job {job_id}: {e}")
        job_data['status'] = 'error'
        job_data['error'] = str(e)
        cache.set(f'job_{job_id}', job_data, timeout=3600)


def progress_page(request, job_id):
    job_data = cache.get(f'job_{job_id}')
    if not job_data:
        return render(request, 'compare/error.html', {'message': 'Job not found or expired.'})
    context = {
        'job_id': job_id,
        'doc1_name': job_data['doc1_name'],
        'doc2_name': job_data['doc2_name'],
        'doc1_pages': job_data['doc1_pages'],
        'doc2_pages': job_data['doc2_pages'],
    }
    return render(request, 'compare/progress.html', context)


def get_progress(request, job_id):
    job_data = cache.get(f'job_{job_id}')
    if not job_data:
        return JsonResponse({'error': 'Job not found'}, status=404)

    response = {
        'status': job_data['status'],
        'progress': job_data['progress'],
        'elapsed': time.time() - job_data['start_time'],
    }
    if job_data['status'] == 'done':
        response.update({
            'similarity': job_data['similarity'],
            'diff_text': job_data['diff_text'],
            'total_time': job_data['total_time'],
            'doc1_id': job_data['doc1_id'],
            'doc2_id': job_data['doc2_id'],
            'toc_comparison': job_data.get('toc_comparison'),
        })
    elif job_data['status'] == 'error':
        response['error'] = job_data.get('error', 'Unknown error')
    return JsonResponse(response)


def result_page(request, job_id):
    """Display the final comparison result."""
    job_data = cache.get(f'job_{job_id}')
    if not job_data or job_data.get('status') != 'done':
        return render(request, 'compare/error.html', {'message': 'Result not ready or expired.'})

    doc1 = PDFDocument.objects.get(id=job_data['doc1_id'])
    doc2 = PDFDocument.objects.get(id=job_data['doc2_id'])

    context = {
        'doc1': doc1,
        'doc2': doc2,
        'doc1_pages': job_data.get('doc1_pages', '?'),
        'doc2_pages': job_data.get('doc2_pages', '?'),
        'similarity': job_data.get('similarity', 0),
        'diff_text': job_data.get('diff_text', ''),
        'comparison_type': job_data.get('comparison_type', 'full'),
        'total_time': job_data.get('total_time', 0),
        'toc_comparison': job_data.get('toc_comparison'),
    }
    return render(request, 'compare/result.html', context)