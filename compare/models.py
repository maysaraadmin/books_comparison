from django.db import models

class PDFDocument(models.Model):
    title = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Structured data – use models.JSONField (works with SQLite, PostgreSQL, etc.)
    content = models.TextField(blank=True, default='')
    index = models.JSONField(default=dict, blank=True)      # TOC as dict: {level, title, page}
    chapters = models.JSONField(default=list, blank=True)   # List of dicts: {title, start_page, end_page, text}

    def __str__(self):
        return self.title or self.file.name