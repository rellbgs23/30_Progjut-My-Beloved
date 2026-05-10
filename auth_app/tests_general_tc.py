import re
from pathlib import Path

from cryptography.fernet import Fernet
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_app.models import Staff, UserAccount
from medical_app.models import Appointment, Encounter, Patient
from pharmacy_app.models import Medicine, Prescription, PrescriptionItem
from pharmacy_app.utils import sign_prescription


TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
class Tugas3GeneralSecurityTestCases(TestCase):
    def setUp(self):
        self.patient_user = UserAccount.objects.create_user(
            username="patient_general",
            password="StrongPassword123!",
            is_patient=True,
            mfaEnabled=False,
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
            mrn="MRN-GENERAL-01",
            name="General Patient",
            dateOfBirth="1999-01-01",
            address="Jl. Test 1",
            phoneNumber="08123456789",
        )

        self.doctor_user = UserAccount.objects.create_user(
            username="doctor_general",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        self.doctor = Staff.objects.create(
            user=self.doctor_user,
            name="Doctor General",
            role="DOCTOR",
        )

        self.registration_user = UserAccount.objects.create_user(
            username="registration_general",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        self.registration = Staff.objects.create(
            user=self.registration_user,
            name="Registration General",
            role="REGISTRATION",
        )

        self.pharmacist_user = UserAccount.objects.create_user(
            username="pharmacist_general",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        self.pharmacist = Staff.objects.create(
            user=self.pharmacist_user,
            name="Pharmacist General",
            role="PHARMACIST",
        )
        self.paracetamol = Medicine.objects.create(name="Paracetamol")
        self.amoxicillin = Medicine.objects.create(name="Amoxicillin")

        self.encounter = Encounter.objects.create(
            patient=self.patient,
            staff=self.doctor,
            complaint="General complaint",
        )
        self.prescription = Prescription.objects.create(encounter=self.encounter)
        PrescriptionItem.objects.create(
            prescription=self.prescription,
            itemId="ITEM-GEN-1",
            medicineName=self.paracetamol,
            dosage="500mg",
            quantity=10,
            instruction="3x sehari",
        )
        sign_prescription(self.prescription)

        self.dispense_encounter = Encounter.objects.create(
            patient=self.patient,
            staff=self.doctor,
            complaint="Follow up",
        )
        self.validated_prescription = Prescription.objects.create(
            encounter=self.dispense_encounter,
            status=Prescription.RxStatus.VALIDATED,
            validatedAt=timezone.now(),
        )
        PrescriptionItem.objects.create(
            prescription=self.validated_prescription,
            itemId="ITEM-GEN-2",
            medicineName=self.amoxicillin,
            dosage="500mg",
            quantity=5,
            instruction="2x sehari",
        )

    def _future_datetime_value(self):
        return (timezone.now() + timezone.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")

    def test_tc_sqli_01_login_bypass_payload_fails(self):
        response = self.client.post(
            reverse("auth_app:login"),
            {
                "username": "' OR '1'='1' --",
                "password": "bebas",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "auth_app/login.html")
        self.assertContains(response, "Username atau password salah")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_tc_sqli_02_union_payload_on_input_does_not_extract_data(self):
        self.client.force_login(self.patient_user)
        payload = "' UNION SELECT username, password, null FROM users --"

        response = self.client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": payload,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Appointment.objects.filter(reason=payload).exists())
        self.assertNotContains(response, "Traceback")
        self.assertNotContains(response, "OperationalError")
        self.assertNotContains(response, "pbkdf2_sha256")

    def test_tc_sqli_03_non_billing_source_uses_orm_not_raw_sql_concat(self):
        root = Path(settings.BASE_DIR)
        scanned_dirs = ["auth_app", "core_app", "medical_app", "pharmacy_app", "progjut_hospital_system"]
        risky_patterns = [
            re.compile(r"\.objects\.raw\s*\("),
            re.compile(r"connection\.cursor\s*\("),
            re.compile(r"\.execute\s*\("),
            re.compile(r"RawSQL\s*\("),
        ]
        findings = []

        for dirname in scanned_dirs:
            for path in (root / dirname).rglob("*.py"):
                if "migrations" in path.parts or path.name.startswith("tests"):
                    continue
                text = path.read_text(encoding="utf-8")
                for pattern in risky_patterns:
                    if pattern.search(text):
                        findings.append(str(path.relative_to(root)))

        self.assertEqual(findings, [])

    def test_tc_ci_01_script_tag_input_is_rejected(self):
        self.client.force_login(self.patient_user)
        payload = "<script>alert('XSS')</script>"

        response = self.client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.filter(reason=payload).exists())
        self.assertNotContains(response, "<script>alert('XSS')</script>", html=True)

    def test_tc_ci_02_html_injection_input_is_rejected(self):
        self.client.force_login(self.patient_user)
        payload = "<h1>Hacked</h1><img src=x onerror=alert(1)>"

        response = self.client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.filter(reason=payload).exists())
        self.assertNotContains(response, "<h1>Hacked</h1>", html=True)

    def test_tc_ci_03_ssti_payload_is_not_executed(self):
        self.client.force_login(self.patient_user)
        payload = "{{7*7}}"

        response = self.client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": payload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.filter(reason=payload).exists())
        self.assertContains(response, "Keluhan hanya boleh")
        self.assertNotContains(response, settings.SECRET_KEY)

    def test_tc_ba_01_password_is_hashed(self):
        user = UserAccount.objects.create_user(
            username="testuser_general",
            password="TestPassword123",
            is_patient=True,
        )

        self.assertNotEqual(user.password, "TestPassword123")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))

    def test_tc_ba_02_account_locks_after_repeated_failed_login(self):
        for index in range(6):
            response = self.client.post(
                reverse("auth_app:login"),
                {
                    "username": "doctor_general",
                    "password": f"WrongPass{index + 1}",
                },
                follow=True,
            )

        self.doctor_user.refresh_from_db()
        self.assertIsNotNone(self.doctor_user.lockedUntil)
        self.assertContains(response, "Akun terkunci sementara")
        self.assertContains(response, "Coba lagi dalam")

    def test_tc_ba_03_old_session_cookie_cannot_access_after_logout(self):
        self.client.force_login(self.patient_user)
        self.assertEqual(self.client.get(reverse("core_app:patient_dashboard")).status_code, 200)
        old_session = self.client.cookies[settings.SESSION_COOKIE_NAME].value

        self.client.post(reverse("auth_app:logout"))

        replay_client = Client()
        replay_client.cookies[settings.SESSION_COOKIE_NAME] = old_session
        response = replay_client.get(reverse("core_app:patient_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("auth_app:login"), response["Location"])

    def test_tc_ba_04_protected_pages_redirect_without_login(self):
        protected_urls = [
            reverse("core_app:patient_dashboard"),
            reverse("core_app:patient_request_appointment"),
            reverse("medical_app:appointment_create"),
            reverse("pharmacy_app:prescription_list"),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("auth_app:login"), response["Location"])

    def test_tc_ba_05_login_error_message_is_generic(self):
        unknown_response = self.client.post(
            reverse("auth_app:login"),
            {"username": "unknown_general", "password": "WrongPass"},
            follow=True,
        )
        wrong_password_response = self.client.post(
            reverse("auth_app:login"),
            {"username": "doctor_general", "password": "WrongPass"},
            follow=True,
        )

        self.assertContains(unknown_response, "Username atau password salah")
        self.assertContains(wrong_password_response, "Username atau password salah")
        self.assertNotContains(unknown_response, "Username tidak ditemukan")
        self.assertNotContains(wrong_password_response, "Password salah")

    def test_tc_csrf_01_post_forms_render_csrf_token(self):
        form_pages = [
            (None, reverse("auth_app:login")),
            (None, reverse("core_app:patient_register")),
            (self.patient_user, reverse("core_app:patient_request_appointment")),
            (self.registration_user, reverse("medical_app:appointment_create")),
            (self.doctor_user, reverse("medical_app:medical_record_create", args=[self.encounter.pk])),
            (self.doctor_user, reverse("pharmacy_app:create_prescription", args=[self.encounter.pk])),
            (self.pharmacist_user, reverse("pharmacy_app:validate_prescription", args=[self.prescription.id])),
            (self.pharmacist_user, reverse("pharmacy_app:dispense_medicine", args=[self.validated_prescription.id])),
        ]

        for user, url in form_pages:
            with self.subTest(url=url):
                client = Client()
                if user is not None:
                    client.force_login(user)
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_tc_csrf_02_invalid_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.patient_user)
        csrf_client.get(reverse("core_app:patient_request_appointment"))

        response = csrf_client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "csrfmiddlewaretoken": "invalid_token_12345",
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": "Kontrol rutin",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "auth_app/forbidden.html")
        self.assertContains(response, "Forbidden Request", status_code=403)
        self.assertFalse(Appointment.objects.filter(reason="Kontrol rutin").exists())

    def test_tc_csrf_03_cross_origin_post_without_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.patient_user)

        response = csrf_client.post(
            reverse("core_app:patient_request_appointment"),
            {
                "doctor": str(self.doctor.id),
                "scheduledAt": self._future_datetime_value(),
                "reason": "CSRF attack attempt",
            },
            HTTP_ORIGIN="http://attacker.example",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "auth_app/forbidden.html")
        self.assertContains(response, "Forbidden Request", status_code=403)
        self.assertFalse(Appointment.objects.filter(reason="CSRF attack attempt").exists())
