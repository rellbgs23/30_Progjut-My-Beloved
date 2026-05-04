from functools import wraps
from django.http import HttpResponseForbidden
from .models import Staff


def staff_role_required(*allowed_roles):
    #decorators memastikan hanya staff dengan role tertentu yang bisa akses view tertentu.
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required.")

            try:
                staff = request.user.staff
            except Staff.DoesNotExist:
                return HttpResponseForbidden("Staff account required.")

            if staff.role not in allowed_roles:
                return HttpResponseForbidden("Access denied.")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator