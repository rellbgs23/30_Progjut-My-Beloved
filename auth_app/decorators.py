"""Role/permission decorators untuk view staff.

Keduanya MENGALIHKAN user ke halaman home dengan flash error, alih-alih
mengembalikan raw `HttpResponseForbidden` plaintext atau halaman denied
statis. Implementasi dipusatkan di `auth_app.helpers.deny_access`.

Catatan: user anonymous tetap di-redirect ke login, sesuai TC-BA-04.
"""

from functools import wraps

from .helpers import deny_access
from .models import Staff


def staff_required(view_func):
    """Izin hanya untuk user yang punya Staff profile (role apapun)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return deny_access(request)
        try:
            request.user.staff
        except Staff.DoesNotExist:
            return deny_access(request, "Halaman ini hanya untuk staff.")
        return view_func(request, *args, **kwargs)

    return wrapper


def staff_role_required(*allowed_roles):
    """Izin hanya untuk staff dengan role yang termasuk `allowed_roles`."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return deny_access(request)

            try:
                staff = request.user.staff
            except Staff.DoesNotExist:
                return deny_access(
                    request, "Akun ini belum punya profil staff."
                )

            if staff.role not in allowed_roles:
                return deny_access(
                    request,
                    "Role Anda tidak memiliki akses ke halaman tersebut.",
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
