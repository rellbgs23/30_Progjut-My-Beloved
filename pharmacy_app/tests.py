from django.test import TestCase
from django.urls import reverse

from auth_app.models import Staff, UserAccount
from medical_app.models import Encounter, Patient
from .models import Prescription, PrescriptionItem
from .utils import sign_prescription


class PharmacySecurityTest(TestCase):
	def setUp(self):
		self.doctor_user = UserAccount.objects.create_user(
			username='doctor1',
			password='password123',
			mfaEnabled=True,
		)
		self.pharmacist_user = UserAccount.objects.create_user(
			username='pharm1',
			password='password123',
			mfaEnabled=True,
		)
		self.receptionist_user = UserAccount.objects.create_user(
			username='reg1',
			password='password123',
			mfaEnabled=True,
		)

		self.doctor_staff = Staff.objects.create(
			user=self.doctor_user,
			name='Doctor One',
			role='DOCTOR',
		)
		self.pharmacist_staff = Staff.objects.create(
			user=self.pharmacist_user,
			name='Pharmacist One',
			role='PHARMACIST',
		)
		Staff.objects.create(
			user=self.receptionist_user,
			name='Registration One',
			role='REGISTRATION',
		)

		self.patient = Patient.objects.create(
			mrn='MRN001',
			name='Patient One',
			dateOfBirth='1990-01-01',
		)
		self.encounter = Encounter.objects.create(
			patient=self.patient,
			staff=self.doctor_staff,
			complaint='Headache',
		)

	def test_tampering_quantity_prevents_validation(self):
		prescription = Prescription.objects.create(encounter=self.encounter)
		PrescriptionItem.objects.create(
			prescription=prescription,
			itemId='ITM001',
			medicineName='Paracetamol',
			dosage='500mg',
			quantity=10,
			instruction='3x sehari',
		)
		sign_prescription(prescription)

		prescription.refresh_from_db()
		self.assertTrue(prescription.verifySignature())

		PrescriptionItem.objects.filter(prescription=prescription).update(quantity=999)

		prescription.refresh_from_db()
		with self.assertRaises(ValueError):
			prescription.validatePrescription()

		prescription.refresh_from_db()
		self.assertEqual(prescription.status, Prescription.RxStatus.CREATED)

	def test_receptionist_cannot_access_validate_endpoint(self):
		prescription = Prescription.objects.create(encounter=self.encounter)
		PrescriptionItem.objects.create(
			prescription=prescription,
			itemId='ITM001',
			medicineName='Amoxicillin',
			dosage='500mg',
			quantity=5,
			instruction='2x sehari',
		)
		sign_prescription(prescription)

		self.client.force_login(self.receptionist_user)
		response = self.client.post(
			reverse('pharmacy_app:validate_prescription', kwargs={'prescription_id': prescription.id}),
		)

		self.assertEqual(response.status_code, 403)

	def test_dispense_requires_validated_status(self):
		prescription = Prescription.objects.create(encounter=self.encounter)

		with self.assertRaises(ValueError):
			prescription.dispenseMedicine(self.pharmacist_staff)
