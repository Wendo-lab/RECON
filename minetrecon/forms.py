from django import forms
from datetime import datetime




class MultiFileUploadForm(forms.Form):
    MONTH_CHOICES = [(i, datetime(1, i, 1).strftime('%B')) for i in range(1, 13)]  # January to December
    

    file1 = forms.FileField(label='Upload Bank Statement Excel File')
    file2 = forms.FileField(label='Upload General Ledger Excel File')
    month = forms.ChoiceField(choices=MONTH_CHOICES, label='Select Month')
    
    




