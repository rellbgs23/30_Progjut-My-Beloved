"""Broken Authentication acceptance tests.

Memetakan ke:
- TC-BA-01  Password hashing verification (white-box)
- TC-BA-02  Brute force / rate limiting
- TC-BA-03  Session token invalidation setelah logout
- TC-BA-04  Akses halaman terproteksi tanpa login
- TC-BA-05  Informasi error yang tidak informatif
"""

from django.contrib.auth.hashers import check_password, identify_hasher
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auth_app.models import Staff, UserAccount


class TC_BA_01_PasswordHashing(TestCase):
    """TC-BA-01  Password tidak pernah disimpan plaintext."""

    def test_password_is_hashed_not_plaintext(self):
        user = UserAccount.objects.create_user(
            username="testuser",
            password="TestPassword123",
        )
        user.refresh_from_db()

        # Field `password` di DB berisi hash, bukan "TestPassword123".
        self.assertNotEqual(user.password, "TestPassword123")
        self.assertNotIn("TestPassword123", user.password)

        # Hash mengikuti format Django: "<algo>$<iterations>$<salt>$<hash>".
        # identify_hasher() akan sukses -> format valid & algoritma terdaftar.
        hasher = identify_hasher(user.password)
        self.assertIsNotNone(hasher)

        # Algoritma default Django adalah pbkdf2_sha256 (aman).
        self.assertTrue(
            user.password.startswith(("pbkdf2_sha256$", "bcrypt$", "argon2$")),
            f"Hash pakai algoritma yang tidak dikenal: {user.password[:20]}...",
        )

        # Verifikasi round-trip: check_password() dengan plaintext tetap True.
        self.assertTrue(check_password("TestPassword123", user.password))


class TC_BA_02_BruteForceRateLimit(TestCase):
    """TC-BA-02  Percobaan login berulang diblokir."""

    def setUp(self):
        # Rate-limit pakai LocMemCache default -> clear antar test.
        cache.clear()
        self.user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=self.user, name="Doctor One", role="DOCTOR")

    def test_account_locked_after_five_wrong_passwords(self):
        # Login 6 kali dengan password salah.
        for i in range(6):
            self.client.post(
                reverse("auth_app:login"),
                {"username": "doctor1", "password": f"WrongPass{i + 1}"},
            )

        self.user.refresh_from_db()
        # Counter mencapai threshold dan akun terkunci.
        self.assertGreaterEqual(self.user.failedLoginAttempts, 5)
        self.assertIsNotNone(self.user.lockedUntil)
        self.assertGreater(self.user.lockedUntil, timezone.now())

    def test_locked_account_rejects_correct_password(self):
        # Paksa akun ke status locked.
        self.user.failedLoginAttempts = 5
        self.user.lockedUntil = timezone.now() + timezone.timedelta(minutes=15)
        self.user.save(update_fields=["failedLoginAttempts", "lockedUntil"])

        response = self.client.post(
            reverse("auth_app:login"),
            {"username": "doctor1", "password": "StrongPassword123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Akun terkunci")


class TC_BA_03_SessionInvalidationAfterLogout(TestCase):
    """TC-BA-03  Session cookie lama tidak bisa dipakai setelah logout."""

    def setUp(self):
        cache.clear()
        self.user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=self.user, name="Doctor One", role="DOCTOR")

    def test_session_cookie_invalid_after_logout(self):
        # Login dan tangkap session cookie.
        self.client.post(
            reverse("auth_app:login"),
            {"username": "doctor1", "password": "StrongPassword123!"},
        )
        old_session = self.client.cookies.get("sessionid")
        self.assertIsNotNone(old_session, "Harusnya session cookie di-set")
        old_value = old_session.value

        # Logout (pakai POST karena @require_POST).
        self.client.post(reverse("auth_app:logout"))

        # Simulasikan attacker replay cookie lama.
        self.client.cookies["sessionid"] = old_value
        response = self.client.get(reverse("auth_app:profile"))

        # Profile view dilindungi @login_required -> redirect ke login.
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.url)


class TC_BA_04_UnauthenticatedAccessBlocked(TestCase):
    """TC-BA-04  Halaman terproteksi tidak bisa diakses tanpa login."""

    def test_patient_endpoints_redirect_anon_to_login(self):
        endpoints = [
            reverse("core_app:patient_dashboard"),
            reverse("core_app:patient_appointments"),
            reverse("core_app:patient_encounters"),
            reverse("core_app:patient_invoices"),
            reverse("core_app:patient_request_appointment"),
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"{url} harus redirect")
            self.assertIn("/auth/login", response.url, f"{url} redirect target salah")

    def test_profile_requires_login(self):
        response = self.client.get(reverse("auth_app:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.url)


class TC_BA_05_GenericErrorMessage(TestCase):
    """TC-BA-05  Pesan error login identik antara username tidak ada vs
    password salah (cegah user enumeration)."""

    def setUp(self):
        cache.clear()
        user = UserAccount.objects.create_user(
            username="doctor1",
            password="StrongPassword123!",
            mfaEnabled=True,
        )
        Staff.objects.create(user=user, name="Doctor One", role="DOCTOR")

    def test_invalid_username_and_wrong_password_show_same_message(self):
        response1 = self.client.post(
            reverse("auth_app:login"),
            {"username": "nonexistentuser", "password": "anything"},
        )
        # Pakai username lain supaya per-username rate-limit tidak
        # menggigit saat test yang kedua.
        response2 = self.client.post(
            reverse("auth_app:login"),
            {"username": "doctor1", "password": "WrongPassword"},
        )

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)

        # Dua-duanya menampilkan pesan yang SAMA.
        msg = "Username atau password salah."
        self.assertContains(response1, msg)
        self.assertContains(response2, msg)

        # TIDAK boleh ada pesan "Username tidak ditemukan" atau semacamnya.
        body1 = response1.content.decode()
        self.assertNotIn("tidak ditemukan", body1.lower())
        self.assertNotIn("tidak terdaftar", body1.lower())
