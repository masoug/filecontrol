from django import forms

class UploadForm(forms.Form):
    #name = forms.CharField(max_length=65535)
    file = forms.FileField()

