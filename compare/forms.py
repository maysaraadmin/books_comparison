from django import forms

class PDFUploadForm(forms.Form):
    doc1 = forms.FileField(label='First PDF')
    doc2 = forms.FileField(label='Second PDF')