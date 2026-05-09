import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class UserAccount(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # membedakan akun eksternal pasien dari akun internal staff.
    is_patient = models.BooleanField(default=False)

    # MFA default akan lebih aman dibuat False.
    # Akun hanya bisa login jika field ini diaktifkan admin.
    mfaEnabled = models.BooleanField(default=False)

    # mitigasi brute-force / credential stuffing.
    failedLoginAttempts = models.PositiveIntegerField(default=0)
    lockedUntil = models.DateTimeField(null=True, blank=True)

    def authenticate_mfa(self, token=None):
        # Pasien eksternal boleh login tanpa MFA internal staff.
        if self.is_patient:
            return True
        return self.mfaEnabled

    def is_locked(self):
        return self.lockedUntil is not None and self.lockedUntil > timezone.now()

    def lock_remaining_seconds(self):
        if not self.is_locked():
            return 0
        return max(0, int((self.lockedUntil - timezone.now()).total_seconds()))

    def lock_account(self, minutes=15):
        self.lockedUntil = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save(update_fields=["failedLoginAttempts", "lockedUntil"])

    def reset_failed_login(self):
        self.failedLoginAttempts = 0
        self.lockedUntil = None
        self.save(update_fields=["failedLoginAttempts", "lockedUntil"])


class Staff(models.Model):
    ROLE_CHOICES = [
        ("REGISTRATION", "Registration"),
        ("DOCTOR", "Doctor"),
        ("PHARMACIST", "Pharmacist"),
        ("CASHIER", "Cashier"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(UserAccount, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.name} - {self.role}"
