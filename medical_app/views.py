"""Medical app views.

View di sini dibagi dua cluster:
1. Operasional klinis — appointment CRUD oleh registration, encounter/record
   CRUD oleh dokter.
2. Dashboard per-role — halaman landing dengan stats + quick actions yang
   ditampilkan sesudah login.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from auth_app.decorators import staff_role_required
from auth_app.helpers import deny_access
from auth_app.models import Staff

from .forms import AppointmentForm, MedicalRecordEntryForm
from .models import Appointment, Encounter, MedicalRecordEntry, Patient


def _get_current_staff(request):
    try:
        return request.user.staff
    except Staff.DoesNotExist:
        return None


# ---------------------------------------------------------------------------
# DOCTOR
# ---------------------------------------------------------------------------


@login_required
@staff_role_required("DOCTOR")
def doctor_dashboard(request):
    """Halaman utama untuk DOCTOR setelah login.

    Menampilkan jadwal hari ini + counts, plus quick links ke list
    appointment/encounter milik sendiri. Dokter tidak pernah melihat
    data pasien milik dokter lain dari dashboard ini.
    """

    staff = _get_current_staff(request)
    today = timezone.localdate()

    todays_appointments = (
        Appointment.objects.filter(doctor=staff, scheduledAt__date=today)
        .select_related("patient")
        .order_by("scheduledAt")
    )

    upcoming_count = Appointment.objects.filter(
        doctor=staff,
        scheduledAt__gte=timezone.now(),
        status="SCHEDULED",
    ).count()

    encounter_count = Encounter.objects.filter(staff=staff).count()

    return render(
        request,
        "medical_app/doctor_dashboard.html",
        {
            "staff": staff,
            "todays_appointments": todays_appointments,
            "upcoming_count": upcoming_count,
            "encounter_count": encounter_count,
            "active_nav": "dashboard",
        },
    )


@login_required
@staff_role_required("DOCTOR")
def doctor_appointments(request):
    staff = _get_current_staff(request)

    appointments = (
        Appointment.objects.filter(doctor=staff)
        .select_related("patient")
        .order_by("-scheduledAt")
    )

    return render(
        request,
        "medical_app/doctor_appointments.html",
        {"appointments": appointments, "active_nav": "appointments"},
    )


@login_required
@staff_role_required("DOCTOR")
def doctor_encounters(request):
    staff = _get_current_staff(request)

    encounters = (
        Encounter.objects.filter(staff=staff)
        .select_related("patient")
        .order_by("-dateTime")
    )

    return render(
        request,
        "medical_app/doctor_encounters.html",
        {"encounters": encounters, "active_nav": "encounters"},
    )


@login_required
@staff_role_required("DOCTOR")
def doctor_encounter_detail(request, encounter_id):
    staff = _get_current_staff(request)

    encounter = get_object_or_404(
        Encounter.objects.select_related("patient"),
        id=encounter_id,
        staff=staff,
    )

    record = MedicalRecordEntry.objects.filter(encounter=encounter).first()
    diagnosis = treatment_plan = notes = "-"
    if record is not None:
        decrypted = record.decrypt_data()
        diagnosis = decrypted["diagnosis"]
        treatment_plan = decrypted["treatmentPlan"]
        notes = decrypted["notes"]

    return render(
        request,
        "medical_app/doctor_encounter_detail.html",
        {
            "encounter": encounter,
            "record": record,
            "diagnosis": diagnosis,
            "treatment_plan": treatment_plan,
            "notes": notes,
            "active_nav": "encounters",
        },
    )


@login_required
@staff_role_required("DOCTOR")
def create_encounter(request, appointment_id):
    """Mulai encounter berdasarkan appointment terjadwal untuk dokter ini."""

    staff = _get_current_staff(request)
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        doctor=staff,
    )

    if request.method == "POST":
        complaint = request.POST.get("complaint", "").strip()
        if not complaint:
            messages.error(request, "Keluhan pasien wajib diisi.")
        else:
            encounter = Encounter.objects.create(
                patient=appointment.patient,
                staff=staff,
                complaint=complaint,
            )
            appointment.status = "COMPLETED"
            appointment.save(update_fields=["status"])
            messages.success(request, "Encounter dibuat. Silakan tulis rekam medis.")
            return redirect(
                "medical_app:medical_record_create", encounter_id=encounter.id
            )

    return render(
        request,
        "medical_app/encounter_form.html",
        {"appointment": appointment, "active_nav": "appointments"},
    )


# ---------------------------------------------------------------------------
# REGISTRATION
# ---------------------------------------------------------------------------


@login_required
@staff_role_required("REGISTRATION")
def registration_dashboard(request):
    today = timezone.localdate()

    todays_appointments = (
        Appointment.objects.filter(scheduledAt__date=today)
        .select_related("patient", "doctor")
        .order_by("scheduledAt")
    )

    total_patients = Patient.objects.count()
    upcoming = Appointment.objects.filter(
        scheduledAt__gte=timezone.now(), status="SCHEDULED"
    ).count()

    return render(
        request,
        "medical_app/registration_dashboard.html",
        {
            "todays_appointments": todays_appointments,
            "total_patients": total_patients,
            "upcoming_count": upcoming,
            "active_nav": "dashboard",
        },
    )


@login_required
@staff_role_required("REGISTRATION")
def registration_appointments(request):
    appointments = (
        Appointment.objects.select_related("patient", "doctor")
        .order_by("-scheduledAt")
    )
    return render(
        request,
        "medical_app/registration_appointments.html",
        {"appointments": appointments, "active_nav": "appointments"},
    )


@login_required
@staff_role_required("REGISTRATION")
def create_appointment(request):
    patients = Patient.objects.all().order_by("name")
    doctors = Staff.objects.filter(role="DOCTOR").order_by("name")

    if request.method == "POST":
        form = AppointmentForm(request.POST)

        if form.is_valid():
            patient = get_object_or_404(
                Patient,
                id=form.cleaned_data["patient_id"],
            )
            doctor = get_object_or_404(
                Staff,
                id=form.cleaned_data["doctor_id"],
                role="DOCTOR",
            )

            appointment = Appointment(
                patient=patient,
                doctor=doctor,
                scheduledAt=form.cleaned_data["scheduledAt"],
                reason=form.cleaned_data["reason"],
            )

            try:
                appointment.full_clean()
                appointment.save()
                messages.success(request, "Appointment created successfully.")
                return redirect(
                    "medical_app:appointment_detail",
                    appointment_id=appointment.id,
                )
            except ValidationError as error:
                # ValidationError.messages adalah list; gabungkan jadi
                # satu kalimat supaya tidak pernah crash menampilkan
                # objek ValidationError mentah ke template.
                messages.error(request, "; ".join(error.messages))
    else:
        form = AppointmentForm()

    return render(
        request,
        "medical_app/appointment_form.html",
        {
            "form": form,
            "patients": patients,
            "doctors": doctors,
            "active_nav": "appointments",
        },
    )


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "doctor"),
        id=appointment_id,
    )

    staff = _get_current_staff(request)
    if staff is None:
        return deny_access(request)

    # REGISTRATION boleh lihat semua appointment. DOCTOR hanya yang
    # diassign ke dirinya. Role lain tidak diizinkan.
    allowed = staff.role in {"REGISTRATION", "DOCTOR"}
    if staff.role == "DOCTOR" and appointment.doctor_id != staff.id:
        allowed = False

    if not allowed:
        return deny_access(
            request, "Anda tidak berhak melihat appointment ini."
        )

    return render(
        request,
        "medical_app/appointment_detail.html",
        {"appointment": appointment, "active_nav": "appointments"},
    )


# ---------------------------------------------------------------------------
# MEDICAL RECORDS (DOCTOR)
# ---------------------------------------------------------------------------


@login_required
@staff_role_required("DOCTOR")
def create_medical_record(request, encounter_id):
    encounter = get_object_or_404(Encounter, id=encounter_id)
    staff = _get_current_staff(request)

    if encounter.staff_id != staff.id:
        return deny_access(
            request,
            "Anda hanya boleh menulis rekam medis untuk encounter milik sendiri.",
        )

    # Cegah dua MedicalRecordEntry untuk encounter yang sama — kalau
    # dokter perlu mengoreksi catatan, harus lewat flow amend terpisah
    # (belum diimplementasi) supaya audit trail tetap utuh.
    existing_record = MedicalRecordEntry.objects.filter(encounter=encounter).first()
    if existing_record is not None:
        messages.info(request, "Medical record untuk encounter ini sudah ada.")
        return redirect(
            "medical_app:medical_record_detail",
            record_id=existing_record.id,
        )

    if request.method == "POST":
        form = MedicalRecordEntryForm(request.POST)

        if form.is_valid():
            record = MedicalRecordEntry(encounter=encounter)
            record.encrypt_data(
                raw_diagnosis=form.cleaned_data["diagnosis"],
                raw_treatment=form.cleaned_data["treatmentPlan"],
                raw_notes=form.cleaned_data["notes"],
            )
            record.save()

            messages.success(request, "Medical record created securely.")
            return redirect(
                "medical_app:medical_record_detail", record_id=record.id
            )
    else:
        form = MedicalRecordEntryForm()

    return render(
        request,
        "medical_app/record_form.html",
        {"form": form, "encounter": encounter, "active_nav": "encounters"},
    )


@login_required
@staff_role_required("DOCTOR")
def medical_record_detail(request, record_id):
    record = get_object_or_404(MedicalRecordEntry, id=record_id)
    staff = _get_current_staff(request)

    if record.encounter.staff_id != staff.id:
        return deny_access(
            request,
            "Anda hanya boleh membaca rekam medis pasien Anda sendiri.",
        )

    decrypted_data = record.decrypt_data()

    return render(
        request,
        "medical_app/record_detail.html",
        {
            "record": record,
            "diagnosis": decrypted_data["diagnosis"],
            "treatmentPlan": decrypted_data["treatmentPlan"],
            "notes": decrypted_data["notes"],
            "active_nav": "encounters",
        },
    )
