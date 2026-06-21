from django.contrib import admin
from .models import PDFDocument

@admin.register(PDFDocument)
class PDFDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'file', 'uploaded_at')
    readonly_fields = ('content', 'index', 'chapters')   # prevent accidental edits
    search_fields = ('title', 'content')