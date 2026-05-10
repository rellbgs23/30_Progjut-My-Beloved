from django import forms
from .models import Medicine


class PrescriptionItemForm(forms.Form):
    medicineName = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        empty_label='Choose medicine',
    )
    dosage = forms.CharField(max_length=100)
    quantity = forms.IntegerField(min_value=1)
    instruction = forms.CharField(max_length=1000)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicineName'].queryset = Medicine.objects.all()

    def clean_dosage(self):
        value = self.cleaned_data['dosage'].strip()
        if not value:
            raise forms.ValidationError('Dosage is required.')
        return value

    def clean_instruction(self):
        return self.cleaned_data['instruction'].strip()
