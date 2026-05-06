import re

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from auth_app.models import Staff, UserAccount
from medical_app.models import Appointment, Patient


PROFILE_NAME_REGEX = re.compile(r"^[A-Za-z0-9 .,'-]+$")
PROFILE_ADDRESS_REGEX = re.compile(r"^[A-Za-z0-9 .,'#/-]+$")
PROFILE_PHONE_REGEX = re.compile(r"^[0-9+()\- ]+$")


class SelfRegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    full_name = forms.CharField(max_length=255)
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    address = forms.CharField(max_length=255)
    phone_number = forms.CharField(max_length=30)

    def clean_full_name(self):
        value = self.cleaned_data["full_name"].strip()
        if not PROFILE_NAME_REGEX.fullmatch(value):
            raise ValidationError("Nama hanya boleh berisi huruf, angka, spasi, dan tanda baca dasar.")
        return value

    def clean_address(self):
        value = self.cleaned_data["address"].strip()
        if not PROFILE_ADDRESS_REGEX.fullmatch(value):
            raise ValidationError("Alamat mengandung karakter yang tidak diizinkan.")
        return value

    def clean_phone_number(self):
        value = self.cleaned_data["phone_number"].strip()
        if not PROFILE_PHONE_REGEX.fullmatch(value):
            raise ValidationError("No. telepon hanya boleh berisi angka dan simbol +()- spasi.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Konfirmasi password tidak cocok.")

        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                self.add_error("password", error)

        return cleaned_data

    @transaction.atomic
    def save(self):
        user = UserAccount.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            is_patient=True,
            mfaEnabled=False,
        )

        patient = Patient.objects.create(
            user=user,
            mrn=Patient.generate_mrn(),
            name=self.cleaned_data["full_name"],
            dateOfBirth=self.cleaned_data["date_of_birth"],
            address=self.cleaned_data["address"],
            phoneNumber=self.cleaned_data["phone_number"],
        )

        return user, patient


class PatientAppointmentRequestForm(forms.ModelForm):
    doctor = forms.ModelChoiceField(
        queryset=Staff.objects.none(),
        empty_label="Pilih dokter",
    )

    class Meta:
        model = Appointment
        fields = ["doctor", "scheduledAt", "reason"]
        widgets = {
            "scheduledAt": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = Staff.objects.filter(role="DOCTOR").order_by("name")

    def clean_reason(self):
        value = self.cleaned_data["reason"].strip()
        if not PROFILE_ADDRESS_REGEX.fullmatch(value):
            raise ValidationError("Keluhan hanya boleh berisi karakter aman.")
        return value

    def clean_scheduledAt(self):
        value = self.cleaned_data["scheduledAt"]
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        if value <= timezone.now():
            raise ValidationError("Waktu janji temu harus di masa depan.")
        return value
