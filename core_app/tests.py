from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
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

	def test_patient_cannot_access_other_patient_encounter(self):
		self.client.login(username="patient1", password="StrongPassword123!")

		response = self.client.get(
			reverse("core_app:patient_encounter_detail", args=[self.other_encounter.id])
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
		self.assertTrue(Appointment.objects.filter(patient=self.patient, status="SCHEDULED").exists())

	def test_patient_login_redirects_to_patient_dashboard(self):
		response = self.client.post(reverse("auth_app:login"), {
			"username": "patient1",
			"password": "StrongPassword123!",
		})

		self.assertRedirects(response, reverse("core_app:patient_dashboard"))
