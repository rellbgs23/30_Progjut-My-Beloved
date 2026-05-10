import re

from django import forms
from .models import Medicine


DOSAGE_REGEX = re.compile(r"^[A-Za-z0-9 .,+/%\-]+$")
INSTRUCTION_REGEX = re.compile(r"^[A-Za-z0-9 .,?!'():;#/\-\r\n]+$")


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
        if not DOSAGE_REGEX.fullmatch(value):
            raise forms.ValidationError('Dosage contains unsafe characters.')
        return value

    def clean_instruction(self):
        value = self.cleaned_data['instruction'].strip()
        if not INSTRUCTION_REGEX.fullmatch(value):
            raise forms.ValidationError('Instruction contains unsafe characters.')
        return value
