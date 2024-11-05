from django import forms
from datetime import datetime




class MultiFileUploadForm(forms.Form):
    MONTH_CHOICES = [(i, datetime(1, i, 1).strftime('%B')) for i in range(1, 13)]  # January to December
    # Generate year choices starting from 2015 to the current year
    YEAR_CHOICES = [(year, str(year)) for year in range(2015, datetime.now().year + 1)]

    

    file1 = forms.FileField(label='Upload Bank Statement Excel File')
    file2 = forms.FileField(label='Upload General Ledger Excel File')
    month = forms.ChoiceField(choices=MONTH_CHOICES, label='Select Month')
    year = forms.ChoiceField(choices=YEAR_CHOICES, label='Select Year')
    




