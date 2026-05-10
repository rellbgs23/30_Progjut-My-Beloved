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
        ("PENDING", "Pending"),
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
        default="PENDING",
    )
    have_encounter = models.BooleanField(default=False)

    def clean(self):
        if not self.doctor_id:
            return
        if self.doctor.role != "DOCTOR":
            raise ValidationError("Appointment doctor must have DOCTOR role.")

    def __str__(self):
        return f"{self.patient} with {self.doctor} at {self.scheduledAt}"


class Encounter(models.Model):
    encounterNumber = models.PositiveIntegerField(primary_key=True, editable=False)
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.RESTRICT,
        related_name="encounter",
        null=True,
        blank=True,
    )
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.RESTRICT)
    dateTime = models.DateTimeField(auto_now_add=True)
    complaint = models.TextField()

    def clean(self):
        if self.staff.role != "DOCTOR":
            raise ValidationError("Encounter staff must have DOCTOR role.")
        if self.appointment:
            if self.appointment.doctor_id != self.staff_id:
                raise ValidationError("Encounter appointment must belong to the same doctor.")
            if self.appointment.patient_id != self.patient_id:
                raise ValidationError("Encounter appointment must belong to the same patient.")

    def save(self, *args, **kwargs):
        if self.encounterNumber is None:
            latest_number = (
                Encounter.objects
                .aggregate(models.Max("encounterNumber"))["encounterNumber__max"]
                or 0
            )
            self.encounterNumber = latest_number + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Encounter #{self.encounterNumber} - {self.patient}"


class MedicalRecordEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, db_constraint=False)

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
