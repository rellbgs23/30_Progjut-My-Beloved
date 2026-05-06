import uuid
from django.core.exceptions import ValidationError
from django.db import models
from auth_app.models import Staff, UserAccount
from .crypto import encrypt_text, decrypt_text


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # dipakai jika pasien juga punya akun login.
    user = models.OneToOneField(
        UserAccount,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    mrn = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    dateOfBirth = models.DateField()
    address = models.CharField(max_length=255, blank=True)
    phoneNumber = models.CharField(max_length=30, blank=True)

    @classmethod
    def generate_mrn(cls):
        while True:
            candidate = f"MRN-{uuid.uuid4().hex[:10].upper()}"
            if not cls.objects.filter(mrn=candidate).exists():
                return candidate

    def __str__(self):
        return f"{self.mrn} - {self.name}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("SCHEDULED", "Scheduled"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(
        Staff,
        on_delete=models.RESTRICT,
        related_name="doctor_appointments",
    )
    scheduledAt = models.DateTimeField()
    reason = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="SCHEDULED",
    )

    def clean(self):
        if self.doctor.role != "DOCTOR":
            raise ValidationError("Appointment doctor must have DOCTOR role.")

    def __str__(self):
        return f"{self.patient} with {self.doctor} at {self.scheduledAt}"


class Encounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.RESTRICT)
    dateTime = models.DateTimeField(auto_now_add=True)
    complaint = models.TextField()

    def clean(self):
        if self.staff.role != "DOCTOR":
            raise ValidationError("Encounter staff must have DOCTOR role.")

    def __str__(self):
        return f"Encounter {self.id} - {self.patient}"


class MedicalRecordEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE)

    diagnosis_encrypted = models.TextField()
    treatmentPlan_encrypted = models.TextField()
    notes_encrypted = models.TextField(blank=True)

    createdAt = models.DateTimeField(auto_now_add=True)

    def encrypt_data(self, raw_diagnosis, raw_treatment, raw_notes=""):

        self.diagnosis_encrypted = encrypt_text(raw_diagnosis)
        self.treatmentPlan_encrypted = encrypt_text(raw_treatment)
        self.notes_encrypted = encrypt_text(raw_notes)

    def decrypt_data(self):
        return {
            "diagnosis": decrypt_text(self.diagnosis_encrypted),
            "treatmentPlan": decrypt_text(self.treatmentPlan_encrypted),
            "notes": decrypt_text(self.notes_encrypted),
        }

    def __str__(self):
        return f"Medical Record {self.id}"