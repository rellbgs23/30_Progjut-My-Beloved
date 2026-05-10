from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .forms import SecureLoginForm
from .models import UserAccount


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _login_failure(request, form, message):
    messages.error(request, message)
    return render(request, "auth_app/login.html", {"form": form})


def _remaining_attempts_message(remaining_attempts):
    return (
        "Username atau password salah. "
        f"Sisa percobaan sebelum akun terkunci: {remaining_attempts}."
    )
    
def _default_failed_message():
    return ("Username atau password salah.")


def _lockout_message(user):
    remaining_seconds = user.lock_remaining_seconds()
    remaining_minutes = max(1, (remaining_seconds + 59) // 60)
    return f"Akun terkunci sementara. Coba lagi dalam {remaining_minutes} menit."


@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        messages.info(request, "Anda sudah login.")
        return redirect("landing_page")

    if request.method == "POST":
        form = SecureLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            try:
                user_obj = UserAccount.objects.get(username=username)
            except UserAccount.DoesNotExist:
                return _login_failure(
                    request,
                    form,
                    _default_failed_message()
                )

            if user_obj.is_locked():
                return _login_failure(request, form, _lockout_message(user_obj))

            if user_obj.lockedUntil is not None and user_obj.lockedUntil <= timezone.now():
                user_obj.reset_failed_login()

            user = authenticate(request, username=username, password=password)

            if user is None:
                user_obj.failedLoginAttempts += 1

                if user_obj.failedLoginAttempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                    user_obj.failedLoginAttempts = 1
                    user_obj.lock_account(minutes=LOCKOUT_MINUTES)
                    return _login_failure(request, form, _lockout_message(user_obj))
                else:
                    user_obj.save(update_fields=["failedLoginAttempts"])

                remaining_attempts = MAX_FAILED_LOGIN_ATTEMPTS - user_obj.failedLoginAttempts
                return _login_failure(request, form, _remaining_attempts_message(remaining_attempts))

            if not user.authenticate_mfa():
                return _login_failure(request, form, "Login ditolak. MFA belum aktif.")

            user.reset_failed_login()
            login(request, user)

            if user.is_patient:
                return redirect("core_app:patient_dashboard")

            return redirect("landing_page")

    else:
        form = SecureLoginForm()

    return render(request, "auth_app/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("auth_app:login")


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect("auth_app:login")

    return render(request, "auth_app/profile.html", {
			"user": request.user
		},)


def access_denied_view(request):
    messages.error(request, "Access denied for your role.")
    return redirect("landing_page")


def csrf_failure(request, reason=""):
    return render(
        request,
        "auth_app/forbidden.html",
        status=403,
    )
