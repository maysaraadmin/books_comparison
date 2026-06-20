from django.db import models

class PDFDocument(models.Model):
    title = models.CharField(max_length=200, blank=True)
    file = models.FileField(upload_to='pdfs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or self.file.name