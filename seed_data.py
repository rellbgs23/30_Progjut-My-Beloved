import os
import django
import random
from decimal import Decimal
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'progjut_hospital_system.settings')
django.setup()

from auth_app.models import UserAccount, Staff
from medical_app.models import Patient, Encounter, MedicalRecordEntry
from pharmacy_app.models import Prescription, PrescriptionItem
from billing_app.models import Invoice, Payment


def run_seeder():
    doctors = []
    for i in range(1, 11):
        user, _ = UserAccount.objects.get_or_create(username=f"doc{i}")
        user.set_password("password123")
        user.is_staff = True
        user.mfaEnabled = True
        user.save()
        staff, _ = Staff.objects.get_or_create(
            user=user, defaults={"name": f"Dr. Person {i}", "role": "DOCTOR"})
        doctors.append(staff)

    cashiers = []
    for i in range(1, 11):
        user, _ = UserAccount.objects.get_or_create(username=f"cashier{i}")
        user.set_password("password123")
        user.is_staff = True
        user.mfaEnabled = True
        user.save()
        staff, _ = Staff.objects.get_or_create(
            user=user, defaults={"name": f"Cashier {i}", "role": "CASHIER"})
        cashiers.append(staff)

    pharmacists = []
    for i in range(1, 11):
        user, _ = UserAccount.objects.get_or_create(username=f"pharma{i}")
        user.set_password("password123")
        user.is_staff = True
        user.mfaEnabled = True
        user.save()
        staff, _ = Staff.objects.get_or_create(
            user=user, defaults={"name": f"Pharmacist {i}", "role": "PHARMACIST"})
        pharmacists.append(staff)

    patients = []
    for i in range(1, 11):
        user, _ = UserAccount.objects.get_or_create(
            username=f"patient{i}", defaults={"is_patient": True})
        user.set_password("password123")
        user.save()
        patient, _ = Patient.objects.get_or_create(
            mrn=f"MRN-DATA-{i:03d}",
            defaults={
                "user": user,
                "name": f"Patient Name {i}",
                "dateOfBirth": date(1980 + i, 1, 1),
                "address": f"Street Number {i}",
                "phoneNumber": f"0812345678{i}"
            }
        )
        patients.append(patient)

    for i in range(10):
        enc = Encounter.objects.create(
            patient=patients[i],
            staff=doctors[i],
            complaint=f"Patient complaint number {i}"
        )

        mre = MedicalRecordEntry.objects.create(encounter=enc)
        mre.encrypt_data(
            raw_diagnosis=f"Diagnosis result {i}",
            raw_treatment=f"Treatment plan {i}",
            raw_notes=f"Clinical notes {i}"
        )
        mre.save()

        rx = Prescription.objects.create(encounter=enc, status="CREATED")
        PrescriptionItem.objects.create(
            prescription=rx,
            itemId=f"ITEM-{i}",
            medicineName=f"Medicine {i}",
            dosage="10mg",
            quantity=5,
            instruction="Take twice a day"
        )

        inv = Invoice.objects.create(
            encounter=enc,
            totalAmount=Decimal(f"{(i+1)*50000}.00"),
            status="UNPAID"
        )

        if i >= 5:
            pay = Payment(
                invoice=inv,
                processedBy=cashiers[i],
                paidAmount=inv.totalAmount,
                method="CASH"
            )
            pay.recordPayment()
            inv.markAsPaid()


if __name__ == '__main__':
    run_seeder()
