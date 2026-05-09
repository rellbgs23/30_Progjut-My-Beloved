"""SQL Injection acceptance tests.

Memetakan ke:
- TC-SQLi-01  Login bypass via SQL injection
- TC-SQLi-02  Data extraction via search input
- TC-SQLi-03  Parameterized query verification (white-box)

Semua test di sini berjalan di testserver `Client` dan membandingkan
perilaku runtime dengan ekspektasi pada dokumen TC.
"""

import re
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from auth_app.models import Staff, UserAccount


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TC_SQLi_01_LoginBypass(TestCase):
    """TC-SQLi-01  Login Bypass via SQL Injection.

    Mencoba payload klasik seperti `' OR '1'='1' --` pada field username
    maupun password. Login harus GAGAL, HTTP 200, pesan generik, dan
    TIDAK ada redirect ke dashboard.
    """

    def setUp(self):
        cache.clear()
        self.user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=self.user, name="Doctor One", role="DOCTOR")

    def _attempt(self, username, password):
        return self.client.post(
            reverse("auth_app:login"),
            {"username": username, "password": password},
        )

    def test_classic_or_1_eq_1_payload_on_username(self):
        response = self._attempt("' OR '1'='1' --", "bebas")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username atau password salah")

    def test_classic_or_1_eq_1_payload_on_password(self):
        response = self._attempt("doctor1", "' OR '1'='1' --")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username atau password salah")

    def test_quote_terminator_does_not_yield_redirect(self):
        response = self._attempt("admin'--", "anything")
        # Kegagalan login TIDAK boleh di-redirect; tetap render halaman
        # login dengan status 200 agar attacker tidak bisa menebak
        # eksistensi user dari perbedaan kode status.
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("dashboard", response["Content-Type"].lower())


class TC_SQLi_02_UnionSearch(TestCase):
    """TC-SQLi-02  Data Extraction via Search Input.

    Aplikasi ini belum menyediakan endpoint pencarian bebas-teks. Namun
    kita tetap melakukan pembuktian: aplikasi TIDAK pernah meneruskan
    input user mentah ke SQL string. Parameter URL `<uuid:...>` hanya
    menerima bentuk UUID valid; payload UNION lain dibalas 404 oleh
    URL resolver tanpa sentuh database.
    """

    def setUp(self):
        user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=user, name="Doctor One", role="DOCTOR")

    def test_union_payload_on_record_url_returns_404_without_sql_error(self):
        self.client.login(username="doctor1", password="StrongPassword123!")

        payload = "1' UNION SELECT username, password, null FROM users --"
        response = self.client.get(f"/medical/records/{payload}/")

        self.assertEqual(response.status_code, 404)
        body = response.content.decode().lower()
        # TIDAK boleh membocorkan stack trace, nama kolom DB, atau
        # fragment dari tabel `users`.
        self.assertNotIn("traceback", body)
        self.assertNotIn("pbkdf2", body)
        self.assertNotIn("select", body)

    def test_union_payload_on_appointment_url_returns_404(self):
        self.client.login(username="doctor1", password="StrongPassword123!")

        payload = "' OR 1=1 UNION SELECT * FROM auth_app_useraccount --"
        response = self.client.get(f"/medical/appointments/{payload}/")

        self.assertEqual(response.status_code, 404)


class TC_SQLi_03_ParameterizedQueriesWhiteBox(TestCase):
    """TC-SQLi-03  Parameterized Query Verification (White-box).

    Static scan seluruh source code untuk pola berbahaya:
    - f-string dengan SELECT/INSERT/UPDATE/DELETE + nama variabel
    - `.format(...)` pada query SQL
    - concatenation '%' dengan string SQL
    - cursor.execute dengan argumen tunggal (tanpa tuple param)

    Folder yang dipindai: auth_app, billing_app, core_app, medical_app,
    pharmacy_app. Hasil harus KOSONG — semua akses DB lewat ORM.
    """

    CODE_DIRS = [
        "auth_app",
        "billing_app",
        "core_app",
        "medical_app",
        "pharmacy_app",
    ]

    # Pola yang kita anggap sebagai smell raw-SQL dengan input user.
    DANGEROUS_PATTERNS = [
        # f"SELECT ... {var}"
        re.compile(r'f["\'][^"\']*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"\']*\{[^}]+\}', re.IGNORECASE),
        # "SELECT ..." + var  atau  var + "SELECT ..."
        re.compile(r'["\'][^"\']*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"\']*["\']\s*\+', re.IGNORECASE),
        re.compile(r'\+\s*["\'][^"\']*\b(SELECT|INSERT|UPDATE|DELETE)\b', re.IGNORECASE),
        # "SELECT ... %s" % var   (single % formatting on SQL string)
        re.compile(r'["\'][^"\']*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"\']*%s[^"\']*["\']\s*%\s*', re.IGNORECASE),
        # .format(...) on a SQL-looking string
        re.compile(r'["\'][^"\']*\b(SELECT|INSERT|UPDATE|DELETE)\b[^"\']*["\']\s*\.\s*format\s*\(', re.IGNORECASE),
    ]

    def test_no_raw_sql_with_string_concatenation(self):
        offenses = []

        for directory in self.CODE_DIRS:
            for path in (PROJECT_ROOT / directory).rglob("*.py"):
                # Lewati file test -- kita memang boleh bikin SQL-looking
                # string di sini untuk mendokumentasikan contoh vulnerable.
                if path.name.startswith("test_") or "/tests" in str(path):
                    continue
                if "migrations" in path.parts:
                    continue
                source = path.read_text(encoding="utf-8")
                for pattern in self.DANGEROUS_PATTERNS:
                    if pattern.search(source):
                        offenses.append(f"{path.relative_to(PROJECT_ROOT)}  <- {pattern.pattern[:50]}...")

        self.assertEqual(
            offenses,
            [],
            "Ditemukan pola raw-SQL yang berpotensi injectable:\n" + "\n".join(offenses),
        )

    def test_cursor_execute_always_uses_param_tuple(self):
        """Jika ada cursor.execute, argumen kedua (params) HARUS ada."""

        offenses = []
        # cursor.execute("<sql>") tanpa argumen kedua = potensi SQLi.
        pattern = re.compile(
            r'cursor\.execute\s*\(\s*(["\'].*?["\'])\s*\)',
            re.DOTALL,
        )

        for directory in self.CODE_DIRS:
            for path in (PROJECT_ROOT / directory).rglob("*.py"):
                if "migrations" in path.parts:
                    continue
                source = path.read_text(encoding="utf-8")
                if pattern.search(source):
                    offenses.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(offenses, [], "cursor.execute tanpa params tuple")
