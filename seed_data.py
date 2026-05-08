"""Seed data untuk demo/dev environment.

Bikin:
- doc1..doc10      (DOCTOR)
- cashier1..cashier10 (CASHIER)
- pharma1..pharma10   (PHARMACIST)
- patient1..patient10 (pasien, punya Patient record)
- 1 superuser 'admin' / 'hitam123'
- beberapa appointment, encounter, medical record, prescription, invoice

Semua password: hitam123

Jalankan:
    python manage.py flush   # kosongkan DB lebih dulu (ketik 'yes')
    python seed_data.py
"""

import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "progjut_hospital_system.settings")
django.setup()

from django.utils import timezone

from auth_app.models import Staff, UserAccount
from billing_app.models import Invoice
from medical_app.models import Appointment, Encounter, MedicalRecordEntry, Patient
from pharmacy_app.models import Prescription, PrescriptionItem
from pharmacy_app.utils import sign_prescription


SEED_PASSWORD = "hitam123"


def _create_staff_set(prefix: str, role: str, count: int = 10) -> list:
    """Bikin `count` staff dengan username prefix{n}, return list Staff."""

    out = []
    for i in range(1, count + 1):
        username = f"{prefix}{i}"
        user, created = UserAccount.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@medicore.test",
                "mfaEnabled": True,
            },
        )
        if created:
            user.set_password(SEED_PASSWORD)
            user.mfaEnabled = True
            user.save(update_fields=["password", "mfaEnabled"])

        staff, _ = Staff.objects.get_or_create(
            user=user,
            defaults={
                "name": f"{prefix.capitalize()} {i}",
                "role": role,
            },
        )
        out.append(staff)
    return out


def _create_patient_set(count: int = 10) -> list:
    out = []
    for i in range(1, count + 1):
        username = f"patient{i}"
        user, created = UserAccount.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@medicore.test",
                "is_patient": True,
                "mfaEnabled": False,
            },
        )
        if created:
            user.set_password(SEED_PASSWORD)
            user.is_patient = True
            user.save(update_fields=["password", "is_patient"])

        patient, _ = Patient.objects.get_or_create(
            user=user,
            defaults={
                "mrn": f"MRN-SEED-{i:03d}",
                "name": f"Patient {i}",
                "dateOfBirth": "1995-01-01",
                "address": f"Jl. Seeder No. {i}",
                "phoneNumber": f"0812000000{i:02d}",
            },
        )
        out.append(patient)
    return out


def _ensure_superuser():
    admin, created = UserAccount.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@medicore.test",
            "is_staff": True,
            "is_superuser": True,
            "mfaEnabled": True,
        },
    )
    if created:
        admin.set_password(SEED_PASSWORD)
        admin.save()
    return admin


def main():
    print("Seeding MediCore demo data...")

    _ensure_superuser()
    doctors = _create_staff_set("doc", "DOCTOR")
    cashiers = _create_staff_set("cashier", "CASHIER")
    pharmacists = _create_staff_set("pharma", "PHARMACIST")
    patients = _create_patient_set()

    # Appointments: tiap pasien punya 1 appointment ke doc1 (besok)
    for i, p in enumerate(patients, start=1):
        Appointment.objects.get_or_create(
            patient=p,
            doctor=doctors[0],
            scheduledAt=timezone.now() + timedelta(days=1, hours=i),
            defaults={"reason": "Consultation", "status": "SCHEDULED"},
        )

    # Encounter + record + prescription + invoice untuk patient1..3
    for i in range(3):
        patient = patients[i]
        doctor = doctors[i]

        enc, created_enc = Encounter.objects.get_or_create(
            patient=patient,
            staff=doctor,
            defaults={"complaint": "Sample complaint for seed."},
        )
        if created_enc:
            # Medical record
            record = MedicalRecordEntry(encounter=enc)
            record.encrypt_data(
                raw_diagnosis=f"Seed diagnosis {i + 1}",
                raw_treatment=f"Seed treatment {i + 1}",
                raw_notes="Seeded medical note (encrypted).",
            )
            record.save()

            # Prescription
            prescription = Prescription.objects.create(encounter=enc)
            PrescriptionItem.objects.create(
                prescription=prescription,
                itemId=f"ITM-{i + 1}",
                medicineName="Paracetamol",
                dosage="500mg",
                quantity=10,
                instruction="3x sehari setelah makan",
            )
            sign_prescription(prescription)

            # Invoice
            Invoice.objects.get_or_create(
                encounter=enc,
                defaults={
                    "totalAmount": Decimal("150000.00"),
                    "status": Invoice.InvoiceStatus.UNPAID,
                },
            )

    print(f"  Doctors:     {len(doctors)}")
    print(f"  Cashiers:    {len(cashiers)}")
    print(f"  Pharmacists: {len(pharmacists)}")
    print(f"  Patients:    {len(patients)}")
    print(f"  Appointments: {Appointment.objects.count()}")
    print(f"  Encounters:   {Encounter.objects.count()}")
    print(f"  Prescriptions: {Prescription.objects.count()}")
    print(f"  Invoices:     {Invoice.objects.count()}")
    print()
    print("All accounts share password: hitam123")
    print("Superuser: admin / hitam123")


if __name__ == "__main__":
    main()
