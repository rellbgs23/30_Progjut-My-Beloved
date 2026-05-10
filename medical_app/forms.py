import re

from django import forms


CLINICAL_TEXT_REGEX = re.compile(r"^[A-Za-z0-9 .,?!'():;#/\-\r\n]+$")


def clean_clinical_text(value, error_message):
    value = value.strip()
    if not CLINICAL_TEXT_REGEX.fullmatch(value):
        raise forms.ValidationError(error_message)
    return value


class MedicalRecordEntryForm(forms.Form):
    diagnosis = forms.CharField(max_length=1000)
    treatmentPlan = forms.CharField(max_length=1000)
    notes = forms.CharField(max_length=2000, required=False)

    def clean_diagnosis(self):
        return clean_clinical_text(
            self.cleaned_data["diagnosis"],
            "Diagnosis hanya boleh berisi karakter klinis aman.",
        )

    def clean_treatmentPlan(self):
        return clean_clinical_text(
            self.cleaned_data["treatmentPlan"],
            "Treatment plan hanya boleh berisi karakter klinis aman.",
        )

    def clean_notes(self):
        value = self.cleaned_data["notes"].strip()
        if value and not CLINICAL_TEXT_REGEX.fullmatch(value):
            raise forms.ValidationError("Notes hanya boleh berisi karakter klinis aman.")
        return value


class EncounterForm(forms.Form):
    complaint = forms.CharField(widget=forms.Textarea, max_length=2000)

    def clean_complaint(self):
        return clean_clinical_text(
            self.cleaned_data["complaint"],
            "Complaint hanya boleh berisi karakter klinis aman.",
        )
