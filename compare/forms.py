from django import forms
from django.core.validators import FileExtensionValidator

class PDFUploadForm(forms.Form):
    doc1 = forms.FileField(
        label='First PDF',
        validators=[FileExtensionValidator(['pdf'])]
    )
    doc2 = forms.FileField(
        label='Second PDF',
        validators=[FileExtensionValidator(['pdf'])]
    )