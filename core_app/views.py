from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
import re

from auth_app.models import Staff
from billing_app.models import Invoice
from medical_app.models import Appointment, Encounter, MedicalRecordEntry, Patient
from pharmacy_app.models import Prescription

from .forms import PatientAppointmentRequestForm, PatientProfileEditForm, SelfRegistrationForm


MAX_ENCOUNTER_SEARCH_LENGTH = 64
CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
ENCOUNTER_NUMBER_RE = re.compile(r"\d+")


def clean_encounter_search_query(raw_query):
	"""
	Normalize patient-supplied search text before using it in ORM filters.

	The query is still passed to Django's parameterized ORM, so SQL injection
	payloads are treated as data. We also remove control characters and cap
	length so the value is safe to display back in the form.
	"""
	query = CONTROL_CHARACTER_RE.sub("", raw_query or "")
	return query.strip()[:MAX_ENCOUNTER_SEARCH_LENGTH]

def home_view(request):
	current_staff = None
	if request.user.is_authenticated and not request.user.is_patient:
		try:
			current_staff = request.user.staff
		except Staff.DoesNotExist:
			current_staff = None

	return render(request, 'core_app/home.html', {"current_staff": current_staff})


def _get_patient_or_forbidden(request):
	if not request.user.is_authenticated:
		messages.error(request, "Please sign in before accessing the patient portal.")
		return None, redirect("auth_app:login")

	if not request.user.is_patient:
		messages.error(request, "Access denied for your role.")
		return None, redirect("landing_page")

	try:
		return request.user.patient, None
	except Patient.DoesNotExist:
		messages.error(request, "Patient profile not found.")
		return None, redirect("landing_page")


def self_register(request):
	if request.user.is_authenticated:
		messages.info(request, "Anda sudah login.")
		return redirect("landing_page")

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
def edit_patient_profile(request, patient_id):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	if patient.id != patient_id:
		messages.error(request, "Access denied for this patient profile.")
		return redirect("core_app:patient_dashboard")

	if request.method == "POST":
		form = PatientProfileEditForm(request.POST, instance=patient)
		if form.is_valid():
			form.save()
			messages.success(request, "Profil pasien berhasil diperbarui.")
			return redirect("core_app:patient_dashboard")
	else:
		form = PatientProfileEditForm(instance=patient)

	return render(
		request,
		"core_app/patient_edit.html",
		{
			"form": form,
			"patient": patient,
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
			appointment.status = "PENDING"
			appointment.save()
			messages.success(request, "Permintaan janji temu berhasil dibuat dan menunggu persetujuan.")
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

	search_query = clean_encounter_search_query(request.GET.get("q", ""))
	encounters = (
		Encounter.objects.filter(patient=patient)
		.select_related("staff")
		.order_by("-dateTime")
	)

	if search_query:
		if ENCOUNTER_NUMBER_RE.fullmatch(search_query):
			encounters = encounters.filter(encounterNumber=int(search_query))
		else:
			encounters = encounters.none()

	return render(
		request,
		"core_app/encounter_list.html",
		{
			"encounters": encounters,
			"search_query": search_query,
		},
	)


@login_required
def patient_encounter_detail(request, encounter_id):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	encounter = get_object_or_404(
		Encounter.objects.select_related("staff"),
		pk=encounter_id,
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
def patient_encounter_detail_by_number(request, encounter_number):
	patient, error_response = _get_patient_or_forbidden(request)
	if error_response:
		return error_response

	encounter = get_object_or_404(
		Encounter.objects.select_related("staff"),
		encounterNumber=encounter_number,
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
