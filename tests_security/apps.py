"""Security acceptance test suite.

Modul ini memuat test case yang memetakan langsung ke daftar Test Case
keamanan pada dokumen PKPL. Setiap kelas test menyertakan TC-ID sebagai
docstring dan nama method yang eksplisit supaya hasil `manage.py test`
dapat langsung dibandingkan dengan matriks TC.

Modul ini tidak punya model sendiri, hanya dijalankan lewat discover.
"""

from django.apps import AppConfig


class SecurityTestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tests_security"
    verbose_name = "Security Acceptance Tests"
