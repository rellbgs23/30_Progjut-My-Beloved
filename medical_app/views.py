from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404

from auth_app.decorators import deny_to_home, staff_role_required
from auth_app.models import Staff

from .forms import EncounterForm, MedicalRecordEntryForm
from .models import Appointment, Encounter, MedicalRecordEntry


def get_current_staff(request):
    try:
        return request.user.staff
    except Staff.DoesNotExist:
        return None


def format_validation_error(error):
    if hasattr(error, "messages"):
        return " ".join(error.messages)
    return str(error)


@login_required
@staff_role_required("REGISTRATION")
def create_appointment(request):
    appointments = (
        Appointment.objects.filter(status="PENDING")
        .select_related("patient", "doctor")
        .order_by("scheduledAt")
    )

    return render(request, "medical_app/appointment_form.html", {"appointments": appointments})


@login_required
@staff_role_required("REGISTRATION")
def review_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, status="PENDING")

    if request.method != "POST":
        return redirect("medical_app:appointment_create")

    action = request.POST.get("action")
    if action == "approve":
        appointment.status = "SCHEDULED"
        message = "Appointment approved and scheduled."
    elif action == "reject":
        appointment.status = "CANCELLED"
        message = "Appointment rejected."
    else:
        messages.error(request, "Invalid appointment action.")
        return redirect("medical_app:appointment_create")

    appointment.save(update_fields=["status"])
    messages.success(request, message)
    return redirect("medical_app:appointment_create")


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "doctor"),
        id=appointment_id,
    )

    staff = get_current_staff(request)

    if staff is None:
        return deny_to_home(request, "Staff account required.")

    allowed = staff.role in ["REGISTRATION", "DOCTOR"]

    if staff.role == "DOCTOR" and appointment.doctor_id != staff.id:
        allowed = False

    if not allowed:
        return deny_to_home(request, "Access denied for your role.")

    can_create_encounter = (
        staff.role == "DOCTOR"
        and appointment.doctor_id == staff.id
        and appointment.status == "SCHEDULED"
        and not appointment.have_encounter
    )

    return render(request, "medical_app/appointment_detail.html", {
        "appointment": appointment,
        "can_create_encounter": can_create_encounter,
    })


@login_required
@staff_role_required("DOCTOR")
def doctor_appointments(request, doctor_id):
    staff = get_current_staff(request)
    if staff.id != doctor_id:
        return deny_to_home(request, "Access denied for this doctor's appointments.")

    appointments = (
        Appointment.objects.filter(doctor_id=doctor_id)
        .select_related("patient", "doctor")
        .order_by("-scheduledAt")
    )

    return render(request, "medical_app/doctor_appointment_list.html", {
        "appointments": appointments,
        "doctor": staff,
    })


@login_required
@staff_role_required("DOCTOR")
def create_encounter_from_appointment(request, appointment_id):
    staff = get_current_staff(request)

    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update().select_related("patient", "doctor"),
            id=appointment_id,
            doctor=staff,
        )

        if appointment.status != "SCHEDULED":
            messages.error(request, "Only scheduled appointments can become encounters.")
            return redirect("medical_app:appointment_detail", appointment_id=appointment.id)

        if appointment.have_encounter or hasattr(appointment, "encounter"):
            messages.error(request, "This appointment already has an encounter.")
            return redirect("medical_app:appointment_detail", appointment_id=appointment.id)

        if request.method == "POST":
            form = EncounterForm(request.POST)

            if form.is_valid():
                encounter = Encounter(
                    appointment=appointment,
                    patient=appointment.patient,
                    staff=staff,
                    complaint=form.cleaned_data["complaint"],
                )

                try:
                    encounter.full_clean()
                    encounter.save()
                    appointment.have_encounter = True
                    appointment.status = "COMPLETED"
                    appointment.save(update_fields=["have_encounter", "status"])
                    messages.success(request, "Encounter created from appointment.")
                    return redirect("medical_app:medical_record_create", encounter_id=encounter.id)
                except ValidationError as error:
                    messages.error(
                        request,
                        f"Encounter could not be created: {format_validation_error(error)}",
                    )
        else:
            form = EncounterForm(initial={"complaint": appointment.reason})

    return render(request, "medical_app/encounter_form.html", {
        "appointment": appointment,
        "form": form,
    })


@login_required
@staff_role_required("DOCTOR")
def create_medical_record(request, encounter_id):
    encounter = get_object_or_404(Encounter, id=encounter_id)
    staff = get_current_staff(request)

    if encounter.staff_id != staff.id:
        return deny_to_home(request, "Access denied for this encounter.")

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
            return redirect("medical_app:medical_record_detail", record_id=record.id)

    else:
        form = MedicalRecordEntryForm()

    return render(request, "medical_app/record_form.html", {"form": form})


@login_required
@staff_role_required("DOCTOR")
def medical_record_detail(request, record_id):
    record = get_object_or_404(MedicalRecordEntry, id=record_id)
    staff = get_current_staff(request)

    if record.encounter.staff_id != staff.id:
        return deny_to_home(request, "Access denied for this medical record.")

    decrypted_data = record.decrypt_data()

    return render(request, "medical_app/record_detail.html", {
        "record": record,
        "diagnosis": decrypted_data["diagnosis"],
        "treatmentPlan": decrypted_data["treatmentPlan"],
        "notes": decrypted_data["notes"],
    })
