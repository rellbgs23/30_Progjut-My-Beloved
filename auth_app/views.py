from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from .forms import SecureLoginForm
from .models import UserAccount


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15

# Pesan error yang SAMA untuk setiap kegagalan kredensial agar tidak
# membocorkan apakah username itu ada atau tidak (user enumeration).
GENERIC_AUTH_ERROR = "Username atau password salah."


def _register_failed_attempt(user_obj: UserAccount) -> None:
    """Naikkan counter kegagalan login secara atomik (cegah race condition).

    Menggunakan F() expression agar increment dikerjakan di level SQL
    (UPDATE ... SET failedLoginAttempts = failedLoginAttempts + 1). Tanpa ini,
    dua request bersamaan bisa sama-sama membaca nilai lama (misal 3) lalu
    sama-sama menulis 4, sehingga pelaku brute-force efektif kehilangan
    satu attempt yang seharusnya terhitung.
    """

    UserAccount.objects.filter(pk=user_obj.pk).update(
        failedLoginAttempts=F("failedLoginAttempts") + 1,
    )
    user_obj.refresh_from_db(fields=["failedLoginAttempts"])

    if user_obj.failedLoginAttempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user_obj.lock_account(minutes=LOCK_DURATION_MINUTES)


@csrf_protect
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="post:username", rate="5/m", method="POST", block=True)
def login_view(request):
    """Login view dengan mitigasi brute-force & user enumeration.

    - Rate-limit per-IP (10/menit) dan per-username (5/menit) via
      django-ratelimit. Limit per-username mencegah distributed brute-force
      dari banyak IP terhadap satu akun.
    - Pesan error yang konsisten agar username tidak bisa di-enumerate.
    - `authenticate()` dipanggil tanpa lebih dulu memeriksa eksistensi user,
      sehingga profile lookup tidak memperbesar perbedaan timing.
    - Counter kegagalan di-increment secara atomik via F() expression.
    """

    if request.method == "POST":
        form = SecureLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            # Cek lock lebih dulu bila user memang ada. Kalau username
            # tidak ada, kita tetap jalankan authenticate() agar waktu
            # respons mirip dengan kasus user exist tapi password salah.
            user_obj = UserAccount.objects.filter(username=username).first()

            if user_obj and user_obj.is_locked():
                messages.error(request, "Akun terkunci sementara. Coba lagi nanti.")
                return render(request, "auth_app/login.html", {"form": form})

            user = authenticate(request, username=username, password=password)

            if user is None:
                if user_obj is not None:
                    _register_failed_attempt(user_obj)
                messages.error(request, GENERIC_AUTH_ERROR)
                return render(request, "auth_app/login.html", {"form": form})

            if not user.authenticate_mfa():
                messages.error(request, "Login ditolak. MFA belum aktif.")
                return render(request, "auth_app/login.html", {"form": form})

            user.reset_failed_login()

            # Django's login() otomatis rotate session key -> cegah
            # session-fixation. Kita set ulang expiry untuk memastikan
            # session baru tunduk pada SESSION_COOKIE_AGE saat ini.
            login(request, user)
            request.session.set_expiry(0)  # gunakan SESSION_COOKIE_AGE default

            if user.is_patient:
                return redirect("core_app:patient_dashboard")

            return redirect("auth_app:profile")

    else:
        form = SecureLoginForm()

    return render(request, "auth_app/login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("auth_app:login")


@login_required(login_url="auth_app:login")
def profile_view(request):
    return render(request, "auth_app/profile.html")


def access_denied_view(request):
    """Render halaman Access Denied dengan HTTP 403.

    Dipakai oleh decorator `user_passes_test` sebagai `login_url`.
    """
    return render(request, "auth_app/denied.html", status=403)
