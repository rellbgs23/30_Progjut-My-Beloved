"""Code injection acceptance tests (XSS / HTML Injection / SSTI).

Memetakan ke:
- TC-CI-01  Script tag injection (reflected / stored XSS)
- TC-CI-02  HTML injection via input field
- TC-CI-03  Template injection (SSTI)
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from auth_app.models import Staff, UserAccount
from medical_app.models import Appointment, Patient


# Fernet key valid (base64 32-byte) agar test yang menulis PHI tidak
# gagal gara-gara encryption setup.
TEST_FERNET_KEY = "4ihV37Q0bSRRZGS-MU1jU1Z3A-aR0YQ-iPC4U97lk3A="


class TC_CI_01_ScriptTagInjection(TestCase):
    """TC-CI-01  Script Tag Injection.

    Payload <script>alert('XSS')</script> tidak boleh dieksekusi; harus
    di-escape atau di-strip oleh server.
    """

    def setUp(self):
        cache.clear()

    def test_registration_name_escaped_via_input_validator(self):
        """Nama dengan payload script ditolak saat validasi, bukan tersimpan."""
        response = self.client.post(
            reverse("core_app:patient_register"),
            {
                "username": "xssuser",
                "email": "xss@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "full_name": "<script>alert('XSS')</script>",
                "date_of_birth": "2000-01-01",
                "address": "Jl. Aman 1",
                "phone_number": "081234567890",
            },
        )
        # Form menolak payload karena nama harus match regex whitelist.
        self.assertEqual(response.status_code, 200)
        # Tidak boleh muncul TAG <script> mentah di HTML response.
        body = response.content.decode()
        self.assertNotIn("<script>alert('XSS')</script>", body)

    @override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
    def test_login_error_message_does_not_reflect_raw_html(self):
        """Pesan error login tidak boleh memantulkan payload HTML mentah."""
        payload = "<script>alert(1)</script>"
        response = self.client.post(
            reverse("auth_app:login"),
            {"username": payload, "password": "wrong"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # Django auto-escape -> payload muncul sebagai entity, BUKAN tag.
        self.assertNotIn("<script>alert(1)</script>", body)


class TC_CI_02_HtmlInjection(TestCase):
    """TC-CI-02  HTML injection via input field."""

    def setUp(self):
        cache.clear()

    def test_html_tag_in_name_is_rejected(self):
        """<h1>Hacked</h1><img ...> harus tidak lolos validator nama."""
        response = self.client.post(
            reverse("core_app:patient_register"),
            {
                "username": "htmluser",
                "email": "html@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "full_name": "<h1>Hacked</h1><img src=x onerror=alert(1)>",
                "date_of_birth": "2000-01-01",
                "address": "Jl. Aman 1",
                "phone_number": "081234567890",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nama hanya boleh")
        # User tidak pernah tercipta.
        self.assertFalse(UserAccount.objects.filter(username="htmluser").exists())

    @override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
    def test_reflected_patient_name_auto_escaped_on_dashboard(self):
        """Nama pasien valid dengan karakter & < > ditampilkan sebagai teks biasa."""
        user = UserAccount.objects.create_user(
            username="anna",
            password="StrongPassword123!",
            is_patient=True,
        )
        Patient.objects.create(
            user=user,
            mrn="MRN-XSS-1",
            name="Anna & Friends",
            dateOfBirth="2000-01-01",
            address="Jl. Amat 1",
            phoneNumber="081234567890",
        )

        self.client.login(username="anna", password="StrongPassword123!")
        response = self.client.get(reverse("core_app:patient_dashboard"))

        # Django auto-escape -> '&' menjadi '&amp;' pada output HTML.
        self.assertEqual(response.status_code, 200)
        self.assertIn("Anna &amp; Friends", response.content.decode())


class TC_CI_03_ServerSideTemplateInjection(TestCase):
    """TC-CI-03  Server-Side Template Injection.

    Payload {{7*7}} harus tampil literal "{{7*7}}", BUKAN "49".
    """

    def setUp(self):
        cache.clear()

    def test_template_expression_in_login_username_not_evaluated(self):
        response = self.client.post(
            reverse("auth_app:login"),
            {"username": "{{7*7}}", "password": "anything"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # Payload muncul literal (di-escape), BUKAN hasil evaluasinya.
        self.assertNotIn(">49<", body)
        self.assertNotIn("config.SECRET_KEY", body)

    def test_template_expression_in_registration_name_rejected_or_escaped(self):
        response = self.client.post(
            reverse("core_app:patient_register"),
            {
                "username": "sstiuser",
                "email": "ssti@example.com",
                "password": "StrongPassword123!",
                "confirm_password": "StrongPassword123!",
                "full_name": "{{7*7}}",
                "date_of_birth": "2000-01-01",
                "address": "Jl. Aman 1",
                "phone_number": "081234567890",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Form menolak karena `{{` dan `}}` tidak match regex whitelist.
        self.assertFalse(UserAccount.objects.filter(username="sstiuser").exists())

    def test_secret_key_never_rendered_in_any_response(self):
        """Endpoint manapun tidak boleh merender SECRET_KEY ke response."""
        from django.conf import settings

        secret = settings.SECRET_KEY
        paths = [
            reverse("auth_app:login"),
            reverse("core_app:patient_register"),
        ]
        for path in paths:
            r = self.client.get(path)
            self.assertNotIn(
                secret,
                r.content.decode(),
                f"SECRET_KEY bocor di {path}",
            )
