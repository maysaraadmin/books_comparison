from django import forms
from django.core.validators import FileExtensionValidator

COMPARISON_CHOICES = [
    ('full', 'Full Text (whole document)'),
    ('toc', 'Table of Contents (Index) only'),
    ('chapters', 'Chapters content only'),
    ('toc_chapters', 'Index + Chapters combined'),
    ('toc_titles', 'Compare Chapter Titles only'),   # NEW
]

class PDFUploadForm(forms.Form):
    doc1 = forms.FileField(
        label='First PDF',
        validators=[FileExtensionValidator(['pdf'])]
    )
    doc2 = forms.FileField(
        label='Second PDF',
        validators=[FileExtensionValidator(['pdf'])]
    )
    comparison_type = forms.ChoiceField(
        choices=COMPARISON_CHOICES,
        widget=forms.RadioSelect,
        initial='full',
        label='Compare which part?'
    )