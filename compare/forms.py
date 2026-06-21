from django import forms
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

COMPARISON_CHOICES = [
    ('full', 'Full Text (whole document)'),
    ('toc', 'Table of Contents (Index) only'),
    ('chapters', 'Chapters content only'),
    ('toc_chapters', 'Index + Chapters combined'),
    ('toc_titles', 'Compare Chapter Titles only'),   # NEW
]

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB total for both files

def validate_file_size(file):
    if file.size > MAX_UPLOAD_SIZE:
        raise ValidationError(f'File size exceeds {MAX_UPLOAD_SIZE // (1024*1024)}MB limit.')

class PDFUploadForm(forms.Form):
    doc1 = forms.FileField(
        label='First PDF',
        validators=[FileExtensionValidator(['pdf']), validate_file_size]
    )
    doc2 = forms.FileField(
        label='Second PDF',
        validators=[FileExtensionValidator(['pdf']), validate_file_size]
    )
    comparison_type = forms.ChoiceField(
        choices=COMPARISON_CHOICES,
        widget=forms.RadioSelect,
        initial='full',
        label='Compare which part?'
    )

    def clean(self):
        cleaned_data = super().clean()
        doc1 = cleaned_data.get('doc1')
        doc2 = cleaned_data.get('doc2')

        if doc1 and doc2:
            total_size = doc1.size + doc2.size
            if total_size > MAX_TOTAL_SIZE:
                raise ValidationError(f'Total size of both files exceeds {MAX_TOTAL_SIZE // (1024*1024)}MB limit.')

        return cleaned_data