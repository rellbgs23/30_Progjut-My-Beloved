from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.urls import reverse

from auth_app.models import UserAccount, Staff
from .models import Patient, Encounter, MedicalRecordEntry


TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(FIELD_ENCRYPTION_KEY=TEST_FERNET_KEY)
class MedicalSecurityTests(TestCase):
    def setUp(self):
        self.doctor_user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )

        self.doctor_staff = Staff.objects.create(
            user=self.doctor_user,
            name="Doctor One",
            role="DOCTOR",
        )

        self.pharmacist_user = UserAccount.objects.create_user(
            username="pharmacist1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )

        self.pharmacist_staff = Staff.objects.create(
            user=self.pharmacist_user,
            name="Pharmacist One",
            role="PHARMACIST",
        )

        self.patient = Patient.objects.create(
            mrn="MRN001",
            name="Patient One",
            dateOfBirth="2000-01-01",
        )

        self.encounter = Encounter.objects.create(
            patient=self.patient,
            staff=self.doctor_staff,
            complaint="Headache",
        )

    def test_medical_record_is_stored_encrypted(self):
        record = MedicalRecordEntry(encounter=self.encounter)
        record.encrypt_data(
            raw_diagnosis="Migraine",
            raw_treatment="Rest and medication",
            raw_notes="Sensitive note",
        )
        record.save()

        self.assertNotIn("Migraine", record.diagnosis_encrypted)
        self.assertNotIn("Rest and medication", record.treatmentPlan_encrypted)
        self.assertNotIn("Sensitive note", record.notes_encrypted)

    def test_doctor_can_decrypt_own_medical_record(self):
        self.client.login(username="doctor1", password="StrongPassword123!")

        record = MedicalRecordEntry(encounter=self.encounter)
        record.encrypt_data(
            raw_diagnosis="Migraine",
            raw_treatment="Rest and medication",
            raw_notes="Sensitive note",
        )
        record.save()

        response = self.client.get(
            reverse("medical_app:medical_record_detail", args=[record.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Migraine")
        self.assertContains(response, "Rest and medication")

    def test_non_doctor_cannot_access_medical_record(self):
        self.client.login(username="pharmacist1", password="StrongPassword123!")

        record = MedicalRecordEntry(encounter=self.encounter)
        record.encrypt_data(
            raw_diagnosis="Migraine",
            raw_treatment="Rest and medication",
            raw_notes="Sensitive note",
        )
        record.save()

        response = self.client.get(
            reverse("medical_app:medical_record_detail", args=[record.id])
        )

        # Non-doctor ditolak oleh @staff_role_required decorator yang
        # mengembalikan HttpResponseForbidden (403) langsung.
        self.assertEqual(response.status_code, 403)

    def test_doctor_can_create_medical_record_for_own_encounter(self):
        self.client.login(username="doctor1", password="StrongPassword123!")

        response = self.client.post(
            reverse("medical_app:medical_record_create", args=[self.encounter.id]),
            {
                "diagnosis": "Migraine",
                "treatmentPlan": "Rest and medication",
                "notes": "Sensitive note",
            },
        )

        self.assertEqual(response.status_code, 302)

        record = MedicalRecordEntry.objects.first()
        self.assertIsNotNone(record)
        self.assertNotIn("Migraine", record.diagnosis_encrypted)

    def test_invalid_uuid_payload_does_not_execute_sql_injection(self):
        self.client.login(username="doctor1", password="StrongPassword123!")

        response = self.client.get("/medical/records/1 OR 1=1/")

        self.assertEqual(response.status_code, 404)