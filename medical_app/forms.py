from django import forms


class MedicalRecordEntryForm(forms.Form):
    diagnosis = forms.CharField(max_length=1000)
    treatmentPlan = forms.CharField(max_length=1000)
    notes = forms.CharField(max_length=2000, required=False)


class EncounterForm(forms.Form):
    complaint = forms.CharField(widget=forms.Textarea, max_length=2000)
