"""Pharmacy-specific decorators.

Berbeda dari auth_app.decorators, decorator di sini juga MEREKAM kegagalan
role/MFA ke AuditLog. Ini adalah kontrol compliance — audit trail harus
memperlihatkan siapa yang mencoba akses endpoint sensitif meskipun aksi
tersebut ditolak.

Perilaku respon: seperti auth_app, akses ditolak -> redirect ke home
(kalau sudah login) atau ke login (kalau anon) via
`auth_app.helpers.deny_access`.
"""

from functools import wraps

from auth_app.helpers import deny_access
from auth_app.models import Staff


def pharmacist_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Import di dalam body untuk menghindari circular import pada
        # startup karena billing_app mengimport medical_app dan auth_app.
        from billing_app.models import AuditLog

        if not request.user.is_authenticated:
            return deny_access(request)

        try:
            staff = request.user.staff
        except Staff.DoesNotExist:
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                detail={"reason": "Missing staff profile"},
            )
            return deny_access(
                request, "Akun ini belum punya profil staff."
            )

        if staff.role != "PHARMACIST":
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                actor=staff,
                detail={"requiredRole": "PHARMACIST", "actualRole": staff.role},
            )
            return deny_access(
                request, "Halaman apoteker hanya untuk role PHARMACIST."
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def mfa_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from billing_app.models import AuditLog

        if not request.user.is_authenticated:
            return deny_access(request)

        try:
            actor = request.user.staff
        except Staff.DoesNotExist:
            actor = None

        if not getattr(request.user, "mfaEnabled", False):
            AuditLog.record_action(
                action=AuditLog.Action.AUTH_FAIL,
                actor=actor,
                detail={"reason": "MFA is not enabled"},
            )
            return deny_access(
                request,
                "Aksi ini membutuhkan MFA aktif. Hubungi admin.",
            )

        return view_func(request, *args, **kwargs)

    return wrapper
