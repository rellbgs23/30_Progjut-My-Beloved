from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from billing_app.models import Invoice
from medical_app.models import Appointment, Encounter, MedicalRecordEntry, Patient
from pharmacy_app.models import Prescription

from .forms import PatientAppointmentRequestForm, SelfRegistrationForm

def home_view(request):
    return render(request, 'core_app/home.html')


def _get_patient_or_forbidden(request):
	if not request.user.is_authenticated:
		return None, HttpResponseForbidden("Authentication required.")

	if not request.user.is_patient:
		return None, HttpResponseForbidden("Access denied.")

	try:
		return request.user.patient, None
	except Patient.DoesNotExist:
		return None, HttpResponseForbidden("Patient profile not found.")


def self_register(request):
	if request.user.is_authenticated:
		if request.user.is_patient:
			return redirect("core_app:patient_dashboard")
		return redirect("auth_app:profile")

	if request.method == "POST":
		form = SelfRegistrationForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, "Registrasi berhasil. Silakan login sebagai pasien.")
			return redirect("auth_app:login")
	else:
		form = SelfRegistrationForm()

	return render(request, "core_app/register.html", {"form": form})


@login_required
def patient_dashboard(request):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

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
		},
	)


@login_required
def request_appointment(request):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

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

	return render(request, "core_app/request_appointment.html", {"form": form})


@login_required
def patient_appointments(request):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	appointments = (
		Appointment.objects.filter(patient=patient)
		.select_related("doctor")
		.order_by("-scheduledAt")
	)

	return render(request, "core_app/appointment_list.html", {"appointments": appointments})


@login_required
def patient_encounter_list(request):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	encounters = (
		Encounter.objects.filter(patient=patient)
		.select_related("staff")
		.order_by("-dateTime")
	)

	return render(request, "core_app/encounter_list.html", {"encounters": encounters})


@login_required
def patient_encounter_detail(request, encounter_id):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

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

	prescription = Prescription.objects.filter(encounter=encounter).prefetch_related("items").first()

	return render(
		request,
		"core_app/encounter_detail.html",
		{
			"encounter": encounter,
			"record": record,
			"diagnosis": diagnosis,
			"treatment_plan": treatment_plan,
			"prescription": prescription,
		},
	)


@login_required
def patient_invoices(request):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	invoices = (
		Invoice.objects.filter(
			encounter__patient=patient,
			status__in=[Invoice.InvoiceStatus.UNPAID, Invoice.InvoiceStatus.PAID],
		)
		.select_related("encounter")
		.order_by("-createdAt")
	)

	return render(request, "core_app/invoice_list.html", {"invoices": invoices})
