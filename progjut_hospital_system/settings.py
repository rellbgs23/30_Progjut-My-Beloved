"""
Django settings for progjut_hospital_system project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Load file .env

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(name: str, default: str = "") -> list:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------

# SECURITY: Tidak boleh ada fallback SECRET_KEY. Jika env var tidak
# ter-set, aplikasi HARUS gagal start alih-alih diam-diam memakai kunci lemah.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "DJANGO_SECRET_KEY environment variable is required. "
        "Generate one with: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )

# SECURITY: DEBUG default HARUS False. Developer yang ingin debug
# cukup set DEBUG=True di .env lokal mereka.
DEBUG = _env_bool("DEBUG", default=False)

# SECURITY: ALLOWED_HOSTS harus di-set secara eksplisit di production.
# Untuk DEBUG=True kita izinkan localhost agar dev experience tetap mulus.
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Kunci terpisah untuk signing prescription (HMAC) sehingga rotasi
# SECRET_KEY tidak otomatis menginvalidasi seluruh signature rekam medis,
# dan sebaliknya rotasi signing key tidak menginvalidasi session cookie.
PRESCRIPTION_SIGNING_KEY = os.getenv("PRESCRIPTION_SIGNING_KEY") or SECRET_KEY

# Kunci enkripsi Fernet untuk field PHI (diagnosis, treatment plan, notes).
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "auth_app",
    "medical_app",
    "pharmacy_app",
    "billing_app",
    "core_app",
]

AUTH_USER_MODEL = "auth_app.UserAccount"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "progjut_hospital_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "progjut_hospital_system.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Session & CSRF cookies
# ---------------------------------------------------------------------------

# Session hangus otomatis setelah 30 menit.
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True  # sliding expiration per request user aktif

# Catatan: SESSION_EXPIRE_AT_BROWSER_CLOSE=True membuat SESSION_COOKIE_AGE
# sebagian besar moot karena cookie jadi session-only. Kita pilih berbasis
# waktu saja agar ekspektasi (30 menit idle timeout) jelas dan konsisten.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# SECURITY: cookie hanya boleh dikirim via HTTPS dan tidak boleh diakses JS.
# Di development (DEBUG=True) kita longgarkan agar runserver di http tetap
# bisa dipakai, tapi di production (DEBUG=False) flag ini WAJIB True.
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Bila di-deploy di belakang proxy yang sudah menangani TLS, izinkan daftar
# origin CSRF eksplisit lewat env var (comma-separated, full scheme+host).
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")


# ---------------------------------------------------------------------------
# Security headers (hanya diaktifkan saat bukan DEBUG)
# ---------------------------------------------------------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Production-only: redirect HTTP -> HTTPS + HSTS.
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 hari
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ---------------------------------------------------------------------------
# Authentication redirects
# ---------------------------------------------------------------------------

LOGIN_URL = "auth_app:login"
LOGIN_REDIRECT_URL = "auth_app:profile"
LOGOUT_REDIRECT_URL = "auth_app:login"
