# MediCore — Hospital Information System

Implementasi Tugas 3 Kelompok PKPL (Pengantar Keamanan Perangkat Lunak)
dengan framework Django, berfokus pada praktik **secure coding** untuk
aplikasi multi-role rumah sakit.

## Peran & Alur

| Role           | Kemampuan utama                                                          |
|----------------|--------------------------------------------------------------------------|
| **Patient**    | Registrasi mandiri, minta appointment, lihat rekam medis & invoice.      |
| **Registration** | Buat appointment dari dalam rumah sakit.                               |
| **Doctor**     | Isi encounter, tulis rekam medis (diagnosis, treatment plan, notes).    |
| **Pharmacist** | Validasi & dispense resep digital.                                      |
| **Cashier**    | Catat pembayaran terhadap invoice UNPAID.                               |

## Stack

- **Backend**: Django 5.2, Python 3.11
- **Database**: SQLite (dev) / PostgreSQL (production-ready)
- **Crypto**: `cryptography` (Fernet field encryption), HMAC-SHA256 signatures
- **Rate limiting**: `django-ratelimit` 4.x

## Menjalankan di Lokal

```bash
# 1. Clone & masuk folder
git clone https://github.com/Rafsandeylora/30_Progjut-My-Beloved.git
cd 30_Progjut-My-Beloved

# 2. Virtualenv (Python 3.11+)
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Siapkan .env (salin dari .env.example lalu isi)
cp .env.example .env
# Generate nilai yang diperlukan:
#   DJANGO_SECRET_KEY, PRESCRIPTION_SIGNING_KEY, FIELD_ENCRYPTION_KEY

# 5. Migrasi & jalankan server
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Akses `http://127.0.0.1:8000/` — akan diarahkan otomatis ke halaman login
atau dashboard sesuai role.

## Struktur Proyek

```
progjut_hospital_system/     # Django project (settings, root URLs)
auth_app/                     # UserAccount, Staff, login & MFA
core_app/                     # Portal pasien (self-register, dashboard)
medical_app/                  # Patient, Appointment, Encounter, MedicalRecordEntry
pharmacy_app/                 # Prescription, PrescriptionItem + signature
billing_app/                  # Invoice, Payment, AuditLog (hash chain)
templates/                    # Base templates + partial topbar
static/css/medicore.css       # Design system (warna, typografi, komponen)
```

Semua template meng-extend `templates/base.html` (layout terautentikasi)
atau `templates/base_auth.html` (login/registration), sehingga perubahan
branding/komponen cukup dilakukan sekali di file desain tersebut.

## Implementasi Secure Coding

### 1. Broken Authentication & Session

- Password divalidasi Django's `AUTH_PASSWORD_VALIDATORS` (minimal 10
  karakter, cek kemiripan dengan data user, block common passwords).
- **Rate limit** pada login: 10/menit per-IP & 5/menit per-username via
  `django-ratelimit`.
- **Account lockout** 15 menit setelah 5 kegagalan berturut-turut.
  Increment counter pakai `F()` expression sehingga atomic terhadap race.
- **User enumeration** dihindari dengan pesan error yang identik (dan
  `authenticate()` tetap dipanggil meski username tidak ada, supaya
  timing tidak bocorkan info).
- **MFA flag** wajib untuk internal staff; endpoint sensitif (pharmacy
  validate/dispense) memakai decorator `@mfa_required`.
- Session: `SESSION_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE=Lax`,
  sliding expiration 30 menit.
- Login Django `login()` otomatis rotate session ID (cegah session fixation).

### 2. CSRF Protection

- Global lewat `CsrfViewMiddleware`.
- Semua form `POST` menyertakan `{% csrf_token %}`.
- `CSRF_COOKIE_SECURE`, `HTTPONLY`, `SAMESITE=Lax`.
- `CSRF_TRUSTED_ORIGINS` env-driven untuk deploy di belakang TLS proxy.

### 3. SQL Injection

- Semua query lewat Django ORM (parameterized).
- Path parameter yang bukan UUID otomatis ditolak oleh URL resolver
  (`<uuid:...>`), mencegah raw input ke query layer.

### 4. XSS & Output Encoding

- Django template engine auto-escape semua variable (`{{ }}`).
- Input user (nama, alamat, phone) divalidasi dengan regex whitelist.
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: same-origin`.

### 5. Sensitive Data Protection

- PHI (diagnosis, treatment plan, notes) dienkripsi at-rest dengan
  Fernet (AES-128-CBC + HMAC) sebelum disimpan ke DB.
- Prescription **ditandatangani HMAC-SHA256** meliputi `itemId`,
  `medicineName`, `dosage`, `quantity`, dan `instruction`. Payload
  ter-serialisasi JSON canonical supaya hash reproducible.
- `FIELD_ENCRYPTION_KEY` dan `PRESCRIPTION_SIGNING_KEY` dipisahkan
  dari `DJANGO_SECRET_KEY` sehingga rotasi kunci satu tidak meng-
  invalidasi yang lain.

### 6. Broken Access Control

- Decorator `@staff_role_required(...)` merender halaman Access Denied
  dengan status 403 untuk role yang tidak diizinkan.
- Row-level check di setiap view: dokter hanya dapat melihat encounter
  miliknya, pasien hanya dapat melihat data miliknya (filter di query).
- `processedBy` pada Payment di-inject dari sesi login — tidak pernah
  dari payload form (anti-spoofing).

### 7. Audit Log & Non-repudiation

- `billing_app.AuditLog` membentuk **hash chain** (setiap log membawa
  hash log sebelumnya). Pembangunan chain dilakukan dalam transaction
  + `select_for_update` supaya dua log konkuren tidak menghasilkan
  cabang chain.
- Record dibuat saat login gagal, role check gagal, signature fail,
  payment sukses, validate, dan dispense.

## Test

```bash
# jalankan semua test security
DJANGO_SECRET_KEY=test python manage.py test

# cek konfigurasi production
DJANGO_SECRET_KEY=... DEBUG=False DJANGO_ALLOWED_HOSTS=example.com \
    python manage.py check --deploy
```

## Environment Variables

Lihat `.env.example` untuk daftar lengkap. Singkatnya:

| Variable                    | Wajib | Keterangan                                  |
|-----------------------------|-------|---------------------------------------------|
| `DJANGO_SECRET_KEY`         | ✅    | Fail-fast kalau tidak di-set.               |
| `DEBUG`                     | —     | Default False.                              |
| `DJANGO_ALLOWED_HOSTS`      | prod  | Comma-separated.                            |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | prod | Kalau di belakang reverse proxy TLS.      |
| `PRESCRIPTION_SIGNING_KEY`  | ✅    | HMAC key untuk tanda tangan resep.          |
| `FIELD_ENCRYPTION_KEY`      | ✅    | Fernet key (32-byte base64) untuk PHI.      |
