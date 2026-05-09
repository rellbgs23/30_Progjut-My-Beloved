from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect, render

from auth_app.decorators import deny_to_home, staff_role_required
from auth_app.models import Staff
from billing_app.models import AuditLog
from medical_app.models import Encounter

from .decorators import mfa_required, pharmacist_required
from .forms import PrescriptionItemForm
from .models import Prescription, PrescriptionItem
from .utils import sign_prescription


def get_current_staff(request):
	try:
		return request.user.staff
	except Staff.DoesNotExist:
		return None


@login_required
@staff_role_required('DOCTOR')
def create_prescription(request, encounter_id):
	encounter = get_object_or_404(Encounter, id=encounter_id)
	staff = get_current_staff(request)

	if encounter.staff_id != staff.id:
		return deny_to_home(request, 'Access denied for this encounter.')

	ItemFormSet = formset_factory(PrescriptionItemForm, extra=1, min_num=1, validate_min=True)

	if request.method == 'POST':
		formset = ItemFormSet(request.POST)

		if formset.is_valid():
			with transaction.atomic():
				prescription = Prescription.objects.create(
					encounter=encounter,
					status=Prescription.RxStatus.CREATED,
				)

				for form in formset:
					data = form.cleaned_data
					PrescriptionItem.objects.create(
						prescription=prescription,
						itemId=data['itemId'],
						medicineName=data['medicineName'],
						dosage=data['dosage'],
						quantity=data['quantity'],
						instruction=data['instruction'],
					)

				sign_prescription(prescription)

			messages.success(request, f'Prescription {prescription.id} created securely.')
			return redirect('pharmacy_app:prescription_detail', prescription_id=prescription.id)
	else:
		formset = ItemFormSet()

	return render(
		request,
		'pharmacy_app/prescription_form.html',
		{'encounter': encounter, 'formset': formset},
	)


@login_required
@pharmacist_required
def prescription_list(request):
	prescriptions = (
		Prescription.objects
		.filter(status=Prescription.RxStatus.CREATED)
		.select_related('encounter__patient', 'encounter__staff')
		.prefetch_related('items')
		.order_by('-encounter__dateTime')
	)
	return render(request, 'pharmacy_app/prescription_list.html', {'prescriptions': prescriptions})


@login_required
def prescription_detail(request, prescription_id):
	prescription = get_object_or_404(
		Prescription.objects.select_related('encounter__patient', 'encounter__staff', 'dispensedBy').prefetch_related('items'),
		id=prescription_id,
	)

	staff = get_current_staff(request)
	if staff is None:
		return deny_to_home(request, 'Staff account required.')

	if staff.role not in ['PHARMACIST', 'DOCTOR']:
		return deny_to_home(request, 'Access denied for your role.')

	if staff.role == 'DOCTOR' and prescription.encounter.staff_id != staff.id:
		return deny_to_home(request, 'Access denied for this prescription.')

	return render(request, 'pharmacy_app/prescription_detail.html', {'prescription': prescription})


@login_required
@mfa_required
@pharmacist_required
def validate_prescription(request, prescription_id):
	prescription = get_object_or_404(
		Prescription.objects.prefetch_related('items'),
		id=prescription_id,
		status=Prescription.RxStatus.CREATED,
	)

	if request.method == 'POST':
		staff = get_current_staff(request)

		try:
			with transaction.atomic():
				prescription.validatePrescription()
				prescription.save(update_fields=['status', 'validatedAt'])

				AuditLog.record_action(
					action=AuditLog.Action.VALIDATE,
					actor=staff,
					prescription=prescription,
				)

			messages.success(request, 'Prescription validated successfully.')
			return redirect('pharmacy_app:prescription_detail', prescription_id=prescription.id)
		except ValueError as error:
			AuditLog.record_action(
				action=AuditLog.Action.SIG_FAIL,
				actor=staff,
				prescription=prescription,
				detail={'reason': str(error)},
			)
			messages.error(request, f'Validation failed: {error}')

	return render(request, 'pharmacy_app/validate_prescription.html', {'prescription': prescription})


@login_required
@mfa_required
@pharmacist_required
def dispense_medicine(request, prescription_id):
	prescription = get_object_or_404(
		Prescription,
		id=prescription_id,
		status=Prescription.RxStatus.VALIDATED,
	)

	if request.method == 'POST':
		staff = get_current_staff(request)

		with transaction.atomic():
			prescription.dispenseMedicine(pharmacist=staff)
			prescription.save(update_fields=['status', 'dispensedAt', 'dispensedBy'])

			AuditLog.record_action(
				action=AuditLog.Action.DISPENSE,
				actor=staff,
				prescription=prescription,
				detail={'dispensedAt': prescription.dispensedAt.isoformat()},
			)

		messages.success(request, 'Medicine dispensed successfully.')
		return redirect('pharmacy_app:prescription_detail', prescription_id=prescription.id)

	return render(request, 'pharmacy_app/dispense_medicine.html', {'prescription': prescription})
