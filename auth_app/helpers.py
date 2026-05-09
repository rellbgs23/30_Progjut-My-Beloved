"""Shared access-control helpers.

Kebijakan akses terpusat di sini sehingga semua app mengeluarkan perilaku
yang sama saat akses ditolak:

- Anonymous user               -> redirect ke halaman login.
- Authenticated user tanpa
  role yang dibutuhkan atau
  tanpa MFA                    -> flash error message + redirect ke /
                                  (core_app.home me-route ke dashboard
                                  role-nya masing-masing).

Dengan pola ini user yang sudah login tidak "terlempar" ke halaman
Access Denied statis; mereka diarahkan kembali ke rumah mereka dengan
pesan yang jelas kenapa halaman yang diminta ditolak. Ini sejalan dengan
permintaan UX: "saat login access denied langsung diarahkan ke home".
"""

from django.contrib import messages
from django.shortcuts import redirect


DEFAULT_DENIED_MESSAGE = (
    "Anda tidak memiliki akses ke halaman tersebut."
)


def deny_access(request, reason=None):
    """Respon yang konsisten saat akses ditolak.

    Args:
        request: HttpRequest aktif.
        reason:  optional pesan yang akan di-flash ke session. Bila
                 None, pakai pesan default.
    """

    if not request.user.is_authenticated:
        # Anon -> login. Tidak pakai flash karena session anon lumrah
        # dipakai di banyak tab sekaligus dan flash bisa leak konteks.
        return redirect("auth_app:login")

    messages.error(request, reason or DEFAULT_DENIED_MESSAGE)
    return redirect("core_app:home")
