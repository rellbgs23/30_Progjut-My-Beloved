import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class UserAccount(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mfaEnabled = models.BooleanField(default=True) # OCL Invariant
    
    def authenticate_mfa(self, token):
        # TODO: Implement MFA logic
        pass

class Staff(models.Model):
    ROLE_CHOICES = [
        ('REGISTRATION', 'Registration'),
        ('DOCTOR', 'Doctor'),
        ('PHARMACIST', 'Pharmacist'),
        ('CASHIER', 'Cashier'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)