"""core_app tidak punya model sendiri; admin dibiarkan kosong sengaja.

Catatan: fungsi portal pasien dijalankan sepenuhnya oleh model di app
lain (auth_app.UserAccount, medical_app.Patient, dll).
"""

from django.contrib import admin  # noqa: F401
