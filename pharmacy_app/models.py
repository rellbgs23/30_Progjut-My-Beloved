import uuid
from django.db import models
from medical_app.models import Encounter

class Prescription(models.Model):
    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('VALIDATED', 'Validated'),
        ('DISPENSED', 'Dispensed'),
        ('CANCELLED', 'Cancelled'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CREATED')
    digitalSignature = models.TextField(null=True, blank=True) # <<crypto>>

    def verifySignature(self):
        # TODO: OCL Invariant (status='VALIDATED' implies verifySignature=true)
        pass