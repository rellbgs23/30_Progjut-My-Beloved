"""Patient-facing portal views.

Semua view di sini:
- login-wajib kecuali `self_register` dan `home` (home hanya router).
- memverifikasi bahwa user memiliki flag `is_patient=True` dan memiliki
  instance `Patient`. Tanpa itu akses akan diblok (AccessDenied) — bukan
  di-404-kan — supaya mudah dilacak di audit log dan tidak membingungkan
  staff yang tidak sengaja nyasar ke portal pasien.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from billing_app.models import Invoice
from medical_app.models import Appointment, Encounter, MedicalRecordEntry, Patient
from pharmacy_app.models import Prescription

from .forms import PatientAppointmentRequestForm, SelfRegistrationForm


def _require_patient(request):
    """Return the Patient profile for the current user, or None.

    View lain dapat memanggil ini lalu mengarahkan ke halaman denied
    saat None dikembalikan.
    """

    user = request.user
    if not user.is_authenticated or not getattr(user, "is_patient", False):
        return None

    return Patient.objects.filter(user=user).first()


def _denied(request):
    return redirect("auth_app:denied")


def home(request):
    """Entry point sederhana — arahkan user ke tempat yang sesuai.

    Patient -> dashboard-nya, staff -> halaman sesuai role, anon -> login.
    Ini memastikan URL "/" atau "/patient/" tidak pernah 404, dan
    setiap role melihat halaman yang relevan untuk mereka.
    """

    user = request.user
    if not user.is_authenticated:
        return redirect("auth_app:login")
    if getattr(user, "is_patient", False):
        return redirect("core_app:patient_dashboard")

    staff = getattr(user, "staff", None)
    if staff is not None:
        if staff.role == "DOCTOR":
            return redirect("medical_app:doctor_dashboard")
        if staff.role == "PHARMACIST":
            return redirect("pharmacy_app:prescription_list")
        if staff.role == "CASHIER":
            return redirect("billing_app:cashier_dashboard")
        if staff.role == "REGISTRATION":
            return redirect("medical_app:registration_dashboard")

    if user.is_superuser:
        return redirect("admin:index")

    return redirect("auth_app:profile")


# ---------------------------------------------------------------------------
# Error handlers (404/403/500)
#
# Django memanggil fungsi-fungsi ini untuk error page saat DEBUG=False.
# Kita render template bermerek MediCore alih-alih halaman default yang
# polos agar UX saat salah URL / izin kurang / crash server tetap
# terhubung dengan brand sisa aplikasi.
# ---------------------------------------------------------------------------


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def server_error(request):
    # Render tanpa context processors: beberapa di antaranya butuh DB
    # akses yang bisa jadi sumber error awal. Render minimal supaya
    # template 500 TIDAK memicu 500 lain.
    from django.template import loader

    template = loader.get_template("errors/500.html")
    return HttpResponse(template.render({}, request), status=500)


def self_register(request):
    if request.user.is_authenticated:
        if getattr(request.user, "is_patient", False):
            return redirect("core_app:patient_dashboard")
        return redirect("auth_app:profile")

    if request.method == "POST":
        form = SelfRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Registrasi berhasil. Silakan login sebagai pasien."
            )
            return redirect("auth_app:login")
    else:
        form = SelfRegistrationForm()

    return render(request, "core_app/register.html", {"form": form})


@login_required
def patient_dashboard(request):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    appointment_count = Appointment.objects.filter(patient=patient).count()
    encounter_count = Encounter.objects.filter(patient=patient).count()
    unpaid_invoice_count = Invoice.objects.filter(
        encounter__patient=patient,
        status=Invoice.InvoiceStatus.UNPAID,
    ).count()

    return render(
        request,
        "core_app/dashboard.html",
        {
            "patient": patient,
            "appointment_count": appointment_count,
            "encounter_count": encounter_count,
            "unpaid_invoice_count": unpaid_invoice_count,
            "active_nav": "dashboard",
        },
    )


@login_required
def request_appointment(request):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    if request.method == "POST":
        form = PatientAppointmentRequestForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient
            appointment.status = "SCHEDULED"
            appointment.save()
            messages.success(request, "Janji temu berhasil dibuat.")
            return redirect("core_app:patient_appointments")
    else:
        form = PatientAppointmentRequestForm()

    return render(
        request,
        "core_app/request_appointment.html",
        {"form": form, "active_nav": "appointments"},
    )


@login_required
def patient_appointments(request):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    appointments = (
        Appointment.objects.filter(patient=patient)
        .select_related("doctor")
        .order_by("-scheduledAt")
    )

    return render(
        request,
        "core_app/appointment_list.html",
        {"appointments": appointments, "active_nav": "appointments"},
    )


@login_required
def patient_appointment_detail(request, appointment_id):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    # Filter by patient sekaligus: kalau appointment ini milik pasien lain,
    # we return 404 supaya tidak bocorkan eksistensi appointment tsb.
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor"),
        id=appointment_id,
        patient=patient,
    )

    return render(
        request,
        "medical_app/appointment_detail.html",
        {"appointment": appointment, "active_nav": "appointments"},
    )


@login_required
def patient_encounter_list(request):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    encounters = (
        Encounter.objects.filter(patient=patient)
        .select_related("staff")
        .order_by("-dateTime")
    )

    return render(
        request,
        "core_app/encounter_list.html",
        {"encounters": encounters, "active_nav": "encounters"},
    )


@login_required
def patient_encounter_detail(request, encounter_id):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    encounter = get_object_or_404(
        Encounter.objects.select_related("staff"),
        id=encounter_id,
        patient=patient,
    )

    record = MedicalRecordEntry.objects.filter(encounter=encounter).first()
    diagnosis = "-"
    treatment_plan = "-"
    if record:
        decrypted = record.decrypt_data()
        diagnosis = decrypted["diagnosis"]
        treatment_plan = decrypted["treatmentPlan"]

    prescription = (
        Prescription.objects.filter(encounter=encounter)
        .prefetch_related("items")
        .first()
    )

    return render(
        request,
        "core_app/encounter_detail.html",
        {
            "encounter": encounter,
            "record": record,
            "diagnosis": diagnosis,
            "treatment_plan": treatment_plan,
            "prescription": prescription,
            "active_nav": "encounters",
        },
    )


@login_required
def patient_invoices(request):
    patient = _require_patient(request)
    if patient is None:
        return _denied(request)

    invoices = (
        Invoice.objects.filter(encounter__patient=patient)
        .select_related("encounter")
        .order_by("-createdAt")
    )

    return render(
        request,
        "core_app/invoice_list.html",
        {"invoices": invoices, "active_nav": "invoices"},
    )
