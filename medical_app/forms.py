from django import forms


class AppointmentForm(forms.Form):
    patient_id = forms.UUIDField()
    doctor_id = forms.UUIDField()
    scheduledAt = forms.DateTimeField()
    reason = forms.CharField(max_length=255)


class MedicalRecordEntryForm(forms.Form):
    diagnosis = forms.CharField(max_length=1000)
    treatmentPlan = forms.CharField(max_length=1000)
    notes = forms.CharField(max_length=2000, required=False)