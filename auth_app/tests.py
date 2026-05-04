from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import UserAccount, Staff


class AuthSecurityTests(TestCase):
    def setUp(self):
        self.user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )

        self.staff = Staff.objects.create(
            user=self.user,
            name="Doctor One",
            role="DOCTOR",
        )

    def test_user_with_mfa_enabled_can_login(self):
        response = self.client.post(reverse("auth_app:login"), {
            "username": "doctor1",
            "password": "StrongPassword123!",
        })

        self.assertEqual(response.status_code, 302)

    def test_user_without_mfa_cannot_login(self):
        self.user.mfaEnabled = False
        self.user.save(update_fields=["mfaEnabled"])

        response = self.client.post(reverse("auth_app:login"), {
            "username": "doctor1",
            "password": "StrongPassword123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MFA belum aktif")

    def test_account_locked_after_five_failed_attempts(self):
        for _ in range(5):
            self.client.post(reverse("auth_app:login"), {
                "username": "doctor1",
                "password": "WrongPassword!",
            })

        self.user.refresh_from_db()

        self.assertEqual(self.user.failedLoginAttempts, 5)
        self.assertIsNotNone(self.user.lockedUntil)
        self.assertGreater(self.user.lockedUntil, timezone.now())

    def test_locked_account_cannot_login_even_with_correct_password(self):
        self.user.failedLoginAttempts = 5
        self.user.lockedUntil = timezone.now() + timezone.timedelta(minutes=15)
        self.user.save(update_fields=["failedLoginAttempts", "lockedUntil"])

        response = self.client.post(reverse("auth_app:login"), {
            "username": "doctor1",
            "password": "StrongPassword123!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Akun terkunci")