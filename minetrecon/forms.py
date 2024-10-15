from django import forms

from django import forms

class MultiFileUploadForm(forms.Form):
    file1 = forms.FileField(label='Upload Bank Statement Excel File')
    file2 = forms.FileField(label='Upload General Ledger Excel File')
    
    
    




