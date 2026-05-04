from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_protect

from .forms import SecureLoginForm
from .models import UserAccount


@csrf_protect
def login_view(request):
    if request.method == "POST":
        form = SecureLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            try:
                user_obj = UserAccount.objects.get(username=username)
            except UserAccount.DoesNotExist:
                messages.error(request, "Username atau password salah.")
                return render(request, "auth_app/login.html", {"form": form})

            if user_obj.is_locked():
                messages.error(request, "Akun terkunci sementara. Coba lagi nanti.")
                return render(request, "auth_app/login.html", {"form": form})

            user = authenticate(request, username=username, password=password)

            if user is None:
                user_obj.failedLoginAttempts += 1

                if user_obj.failedLoginAttempts >= 5:
                    user_obj.lock_account(minutes=15)
                else:
                    user_obj.save(update_fields=["failedLoginAttempts"])

                messages.error(request, "Username atau password salah.")
                return render(request, "auth_app/login.html", {"form": form})

            if not user.authenticate_mfa():
                messages.error(request, "Login ditolak. MFA belum aktif.")
                return render(request, "auth_app/login.html", {"form": form})

            user.reset_failed_login()
            login(request, user)

            return redirect("auth_app:profile")

    else:
        form = SecureLoginForm()

    return render(request, "auth_app/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("auth_app:login")


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect("auth_app:login")

    return render(request, "auth_app/profile.html")