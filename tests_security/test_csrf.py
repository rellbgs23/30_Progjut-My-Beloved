"""CSRF acceptance tests.

Memetakan ke:
- TC-CSRF-01  CSRF token presence on forms
- TC-CSRF-02  Request dengan CSRF token invalid ditolak
- TC-CSRF-03  Simulasi cross-origin request (tanpa token)
"""

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from auth_app.models import Staff, UserAccount
from medical_app.models import Patient


class TC_CSRF_01_TokenPresenceOnForms(TestCase):
    """TC-CSRF-01  Setiap form POST mengandung token CSRF."""

    def setUp(self):
        cache.clear()
        self.user = UserAccount.objects.create_user(
            username="patient1",
            password="StrongPassword123!",
            is_patient=True,
        )
        Patient.objects.create(
            user=self.user,
            mrn="MRN-CSRF-1",
            name="Patient CSRF",
            dateOfBirth="2000-01-01",
        )

    def _assert_csrf_token_in_form(self, url):
        response = self.client.get(url)
        body = response.content.decode()
        self.assertIn(
            'name="csrfmiddlewaretoken"',
            body,
            f"Tidak ada CSRF token di {url}",
        )

    def test_login_form_has_csrf_token(self):
        self._assert_csrf_token_in_form(reverse("auth_app:login"))

    def test_registration_form_has_csrf_token(self):
        self._assert_csrf_token_in_form(reverse("core_app:patient_register"))

    def test_patient_appointment_request_has_csrf_token(self):
        self.client.login(username="patient1", password="StrongPassword123!")
        self._assert_csrf_token_in_form(
            reverse("core_app:patient_request_appointment")
        )


class TC_CSRF_02_InvalidTokenRejected(TestCase):
    """TC-CSRF-02  POST dengan token yang salah dijawab 403.

    Kita gunakan Client(enforce_csrf_checks=True) supaya
    CsrfViewMiddleware aktif seperti di produksi (Django test Client
    default-nya meng-bypass CSRF).
    """

    def setUp(self):
        cache.clear()
        self.user = UserAccount.objects.create_user(
            username="patient1",
            password="StrongPassword123!",
            is_patient=True,
        )
        Patient.objects.create(
            user=self.user,
            mrn="MRN-CSRF-2",
            name="Patient CSRF 2",
            dateOfBirth="2000-01-01",
        )

    def test_post_with_forged_csrf_token_returns_403(self):
        c = Client(enforce_csrf_checks=True)
        c.login(username="patient1", password="StrongPassword123!")

        # Tembak POST dengan token palsu.
        response = c.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": "00000000-0000-0000-0000-000000000000",
                "scheduledAt": "2030-01-01T10:00",
                "reason": "CSRF test",
                "csrfmiddlewaretoken": "invalid_token_12345",
            },
        )

        self.assertEqual(response.status_code, 403)


class TC_CSRF_03_CrossOriginRequestWithoutToken(TestCase):
    """TC-CSRF-03  POST tanpa token sama sekali dijawab 403."""

    def setUp(self):
        cache.clear()
        user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=user, name="Doctor One", role="DOCTOR")

    def test_post_without_csrf_token_is_blocked(self):
        c = Client(enforce_csrf_checks=True)
        c.login(username="doctor1", password="StrongPassword123!")

        # Simulasi form cross-origin: POST biasa tanpa sertakan token.
        response = c.post(
            reverse("auth_app:logout"),
            {},  # tidak kirim csrfmiddlewaretoken
        )

        self.assertEqual(response.status_code, 403)

    def test_login_post_without_csrf_token_is_blocked(self):
        c = Client(enforce_csrf_checks=True)
        response = c.post(
            reverse("auth_app:login"),
            {"username": "doctor1", "password": "anything"},
        )

        self.assertEqual(response.status_code, 403)
