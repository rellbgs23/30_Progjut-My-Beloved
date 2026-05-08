"""Pharmacy-specific decorators.

Berbeda dari auth_app.decorators, decorator di sini juga MEREKAM kegagalan
role/MFA ke AuditLog. Ini adalah kontrol compliance — audit trail harus
memperlihatkan siapa yang mencoba akses endpoint sensitif meskipun aksi
tersebut ditolak.
"""

from functools import wraps

from django.shortcuts import render

from auth_app.models import Staff


def _forbidden(request):
    return render(request, "auth_app/denied.html", status=403)


def pharmacist_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Import di dalam body untuk menghindari circular import pada
        # startup karena billing_app mengimport medical_app dan auth_app.
        from billing_app.models import AuditLog

        if not request.user.is_authenticated:
            return _forbidden(request)

        try:
            staff = request.user.staff
        except Staff.DoesNotExist:
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                detail={"reason": "Missing staff profile"},
            )
            return _forbidden(request)

        if staff.role != "PHARMACIST":
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                actor=staff,
                detail={"requiredRole": "PHARMACIST", "actualRole": staff.role},
            )
            return _forbidden(request)

        return view_func(request, *args, **kwargs)

    return wrapper


def mfa_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from billing_app.models import AuditLog

        if not request.user.is_authenticated:
            return _forbidden(request)

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
            return _forbidden(request)

        return view_func(request, *args, **kwargs)

    return wrapper
