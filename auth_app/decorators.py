"""Role/permission decorators untuk view staff.

Kedua decorator di sini merender halaman denied dengan HTTP 403. Kita
memilih render halaman alih-alih mengembalikan raw `HttpResponseForbidden`
plaintext supaya UX konsisten (tetap ada branding, nav, dan tombol logout),
tapi tetap pakai status 403 supaya test keamanan dan tooling monitoring
dapat membedakan access-denied dari 200/302.
"""

from functools import wraps

from django.shortcuts import render

from .models import Staff


def _forbidden(request):
    return render(request, "auth_app/denied.html", status=403)


def staff_required(view_func):
    """Izin hanya untuk user yang punya Staff profile (role apapun)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _forbidden(request)
        try:
            request.user.staff
        except Staff.DoesNotExist:
            return _forbidden(request)
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_role_required(*allowed_roles):
    """Izin hanya untuk staff dengan role yang termasuk `allowed_roles`."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return _forbidden(request)

            try:
                staff = request.user.staff
            except Staff.DoesNotExist:
                return _forbidden(request)

            if staff.role not in allowed_roles:
                return _forbidden(request)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
