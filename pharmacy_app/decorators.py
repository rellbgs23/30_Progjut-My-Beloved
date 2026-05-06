from functools import wraps
from django.http import HttpResponseForbidden
from auth_app.models import Staff


def pharmacist_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden('Authentication required.')

        from billing_app.models import AuditLog

        try:
            staff = request.user.staff
        except Staff.DoesNotExist:
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                detail={'reason': 'Missing staff profile'},
            )
            return HttpResponseForbidden('Staff account required.')

        if staff.role != 'PHARMACIST':
            AuditLog.record_action(
                action=AuditLog.Action.ROLE_FAIL,
                actor=staff,
                detail={'requiredRole': 'PHARMACIST', 'actualRole': staff.role},
            )
            return HttpResponseForbidden('Only pharmacist can access this feature.')

        return view_func(request, *args, **kwargs)

    return wrapper


def mfa_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseForbidden('Authentication required.')

        from billing_app.models import AuditLog

        actor = None
        try:
            actor = request.user.staff
        except Staff.DoesNotExist:
            actor = None

        if not getattr(request.user, 'mfaEnabled', False):
            AuditLog.record_action(
                action=AuditLog.Action.AUTH_FAIL,
                actor=actor,
                detail={'reason': 'MFA is not enabled'},
            )
            return HttpResponseForbidden('MFA must be enabled for this feature.')

        return view_func(request, *args, **kwargs)

    return wrapper
