from django import forms
from datetime import datetime




class MultiFileUploadForm(forms.Form):
    MONTH_CHOICES = [(i, datetime(1, i, 1).strftime('%B')) for i in range(1, 13)]  # January to December
    # Generate year choices starting from 2022 to the current year
    YEAR_CHOICES = [(year, str(year)) for year in range(2022, datetime.now().year + 1)]

    

    file1 = forms.FileField(label='Upload Bank Statement Excel File')
    file2 = forms.FileField(label='Upload General Ledger Excel File')
    month = forms.ChoiceField(choices=MONTH_CHOICES, label='Select Month')
    year = forms.ChoiceField(choices=YEAR_CHOICES, label='Select Year')
    
class DocumentDownloadForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'placeholder': 'DD/MM/YYYY'}),
        label="Select Date",
        input_formats=['%d/%m/%Y']
    )
    documents = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=[],
        label="Select Button"
    )

    def __init__(self, *args, **kwargs):
        document_choices = kwargs.pop('document_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['documents'].choices = document_choices

