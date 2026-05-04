from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from auth_app.decorators import staff_role_required
from auth_app.models import Staff

from .forms import AppointmentForm, MedicalRecordEntryForm
from .models import Patient, Appointment, Encounter, MedicalRecordEntry


def get_current_staff(request):
    try:
        return request.user.staff
    except Staff.DoesNotExist:
        return None


@login_required
@staff_role_required("REGISTRATION")
def create_appointment(request):
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
                return redirect("medical_app:appointment_detail", appointment_id=appointment.id)
            except ValidationError as error:
                messages.error(request, error)

    else:
        form = AppointmentForm()

    return render(request, "medical_app/appointment_form.html", {"form": form})


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    staff = get_current_staff(request)

    if staff is None:
        return HttpResponseForbidden("Staff account required.")

    allowed = staff.role in ["REGISTRATION", "DOCTOR"]

    if staff.role == "DOCTOR" and appointment.doctor_id != staff.id:
        allowed = False

    if not allowed:
        return HttpResponseForbidden("Access denied.")

    return render(request, "medical_app/appointment_detail.html", {
        "appointment": appointment,
    })


@login_required
@staff_role_required("DOCTOR")
def create_medical_record(request, encounter_id):
    encounter = get_object_or_404(Encounter, id=encounter_id)
    staff = get_current_staff(request)

    if encounter.staff_id != staff.id:
        return HttpResponseForbidden("You can only write records for your own encounter.")

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
        return HttpResponseForbidden("You can only read your own patient's medical record.")

    decrypted_data = record.decrypt_data()

    return render(request, "medical_app/record_detail.html", {
        "record": record,
        "diagnosis": decrypted_data["diagnosis"],
        "treatmentPlan": decrypted_data["treatmentPlan"],
        "notes": decrypted_data["notes"],
    })