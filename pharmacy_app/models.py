import uuid
import hmac
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from medical_app.models import Encounter
from auth_app.models import Staff


class Medicine(models.Model):
    name = models.CharField(max_length=200, primary_key=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Prescription(models.Model):
    class RxStatus(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        VALIDATED = 'VALIDATED', 'Validated'
        DISPENSED = 'DISPENSED', 'Dispensed'
        INVALID = 'INVALID', 'Invalid'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE, db_constraint=False)
    status = models.CharField(max_length=20, choices=RxStatus.choices, default=RxStatus.CREATED)
    digitalSignature = models.TextField(null=True, blank=True) # <<crypto>>
    validatedAt = models.DateTimeField(null=True, blank=True)
    dispensedAt = models.DateTimeField(null=True, blank=True)
    dispensedBy = models.ForeignKey(
        Staff,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='dispensed_prescriptions',
        limit_choices_to={'role': 'PHARMACIST'},
    )

    def clean(self):
        super().clean()

        if self.encounter and self.encounter.staff.role != 'DOCTOR':
            raise ValidationError('Prescription encounter must belong to a DOCTOR.')

    def verifySignature(self):
        from .utils import compute_prescription_signature

        if not self.digitalSignature:
            return False

        expected = compute_prescription_signature(self)
        return hmac.compare_digest(expected, self.digitalSignature)

    def validatePrescription(self):
        if self.status != self.RxStatus.CREATED:
            raise ValueError('Prescription must be CREATED to validate.')

        if not self.verifySignature():
            raise ValueError('Prescription signature validation failed.')

        self.status = self.RxStatus.VALIDATED
        self.validatedAt = timezone.now()

    def dispenseMedicine(self, pharmacist):
        if self.status != self.RxStatus.VALIDATED:
            raise ValueError('Prescription must be VALIDATED before dispensing.')

        if pharmacist.role != 'PHARMACIST':
            raise ValueError('Only pharmacist can dispense medicine.')

        self.status = self.RxStatus.DISPENSED
        self.dispensedAt = timezone.now()
        self.dispensedBy = pharmacist


class PrescriptionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='items')
    itemId = models.CharField(max_length=50, unique=True)
    medicineName = models.ForeignKey(
        Medicine,
        on_delete=models.RESTRICT,
        db_column='medicineName',
        to_field='name',
    )
    dosage = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    instruction = models.TextField()

    def __str__(self):
        return f'{self.medicineName} x{self.quantity} ({self.dosage})'
