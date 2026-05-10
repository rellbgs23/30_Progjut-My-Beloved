from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect

from .models import Staff


def deny_to_home(request, message="Access denied."):
    messages.error(request, message)
    return redirect("landing_page")


def staff_role_required(*allowed_roles):
    #decorators memastikan hanya staff dengan role tertentu yang bisa akses view tertentu.
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, "Please sign in before accessing that page.")
                return redirect("auth_app:login")

            try:
                staff = request.user.staff
            except Staff.DoesNotExist:
                return deny_to_home(request, "Staff account required.")

            if staff.role not in allowed_roles:
                return deny_to_home(request, "Access denied for your role.")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
