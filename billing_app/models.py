import uuid
from django.db import models
from auth_app.models import Staff
from medical_app.models import Encounter

class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE)
    totalAmount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, default='UNPAID') # UNPAID, PAID, VOID

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.RESTRICT)
    processedBy = models.ForeignKey(Staff, on_delete=models.RESTRICT) # OCL: role='CASHIER'
    paidAmount = models.DecimalField(max_digits=12, decimal_places=2)
    paidAt = models.DateTimeField(auto_now_add=True)

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.RESTRICT)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)
    hash = models.CharField(max_length=255) # <<crypto>> (Hash Chaining)