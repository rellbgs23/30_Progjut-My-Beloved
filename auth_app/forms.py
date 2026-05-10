import re

from django import forms
from django.core.exceptions import ValidationError


LOGIN_USERNAME_REGEX = re.compile(r"^[A-Za-z0-9@.+_-]+$")
PASSWORD_SAFE_REGEX = re.compile(r"^[^\s<>`|;&$]+$")


def validate_login_username(value):
    value = value.strip()
    if not LOGIN_USERNAME_REGEX.fullmatch(value):
        raise ValidationError("Username atau password salah.")
    return value


class SecureLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean_username(self):
        return validate_login_username(self.cleaned_data["username"])

    def clean_password(self):
        value = self.cleaned_data["password"]
        if not PASSWORD_SAFE_REGEX.fullmatch(value):
            raise ValidationError("Password mengandung karakter yang tidak diizinkan.")
        return value
