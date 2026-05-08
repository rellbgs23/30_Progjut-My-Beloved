# PKPL26_HospitalSys - Hospital Information System

Repositori ini berisi implementasi Tugas 3 Kelompok untuk mata kuliah Pengantar Keamanan Perangkat Lunak. Aplikasi dibangun dengan Django dan mengambil skenario sistem informasi rumah sakit, dengan fokus utama pada praktik secure coding yang dapat diuji melalui test case SQL Injection, Code Injection/XSS, Broken Authentication, dan CSRF.

## Petunjuk Instalasi Lokal

1. Clone repositori.

   ```bash
   git clone https://gitlab.cs.ui.ac.id/pkpl26/30-progjut-my-beloved/pkpl26_30_progjut-my-beloved.git
   cd PKPL26_HospitalSys
   ```

2. Buat virtual environment.

   Windows:

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

   macOS/Linux:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependency.

   ```bash
   pip install -r requirements.txt
   ```

4. Siapkan file `.env` di root project.

   ```env
   DJANGO_SECRET_KEY=isi_dengan_secret_key_lokal
   FIELD_ENCRYPTION_KEY=isi_dengan_fernet_key
   DEBUG=True
   ```

   Fernet key dapat dibuat dengan:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

5. Jalankan migrasi dan seed data.

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py seed_db
   ```

6. Jalankan server lokal.

   ```bash
   python manage.py runserver
   ```

   Aplikasi dapat diakses melalui `http://127.0.0.1:8000/`.

## A. Deskripsi Aplikasi

PKPL26_HospitalSys adalah sistem informasi rumah sakit sederhana. Aplikasi ini memisahkan alur kerja pasien dan staff internal supaya data medis, resep, appointment, serta pembayaran tidak bercampur di satu akses yang terlalu luas.

Fitur utama:

- Registrasi dan login pasien.
- Dashboard pasien untuk appointment, encounter, rekam medis, dan invoice miliknya sendiri.
- Pengelolaan appointment dan rekam medis oleh role `REGISTRATION` dan `DOCTOR`.
- Pembuatan, validasi, dan dispensing resep oleh `DOCTOR` dan `PHARMACIST`.
- Proses pembayaran invoice oleh `CASHIER`.
- Enkripsi data medis sensitif sebelum disimpan ke database.

Role pengguna:

- `PATIENT`: melihat data dan membuat permintaan appointment untuk dirinya sendiri.
- `REGISTRATION`: mengelola data pendaftaran/appointment sesuai alur registrasi.
- `DOCTOR`: membuat encounter, rekam medis, dan resep.
- `PHARMACIST`: memvalidasi dan memproses resep.
- `CASHIER`: memproses pembayaran invoice.

Stack teknologi:

- Python
- Django
- SQLite untuk environment lokal
- Fernet encryption dari `cryptography`

## B. Pemetaan Secure Coding, CWE, dan Test Case

Catatan untuk potongan kode: snippet secure di bawah ini diambil dari source code aplikasi, lalu dirapikan seperlunya agar fokus pada bagian yang relevan. Snippet tidak secure adalah ilustrasi dari versi rentan yang bisa muncul jika alur yang sama ditulis tanpa praktik secure coding.

### 1. SQL Injection

* **Penjelasan Vulnerability:**

SQL Injection terjadi ketika input user ikut membentuk perintah SQL tanpa pemisahan yang aman antara data dan query. Pada aplikasi rumah sakit, celah ini bisa berakibat serius karena attacker dapat mencoba bypass login, membaca data pasien, atau memanipulasi invoice dan rekam medis. Kerentanan ini terkait dengan CWE-89, Improper Neutralization of Special Elements used in an SQL Command.

Test case yang dicakup:

- `TC-SQLi-01`: login bypass dengan payload seperti `' OR '1'='1`.
- `TC-SQLi-02`: percobaan ekstraksi data melalui payload `UNION SELECT`.
- `TC-SQLi-03`: payload pada endpoint pencarian/filter atau parameter ID, termasuk payload UUID tidak valid.

* **Teknik Mitigasi:**

- Kami membangun akses database melalui Django ORM dan ModelForm, misalnya `UserAccount.objects.get(username=username)`, `Invoice.objects.filter(status=...)`, dan akses relasi melalui ForeignKey.
- Kami memproses input form melalui `cleaned_data`, sehingga value yang masuk sudah melewati validasi Django Form sebelum dipakai oleh logic aplikasi.
- Kami memakai `UUIDField` dan lookup ORM untuk parameter ID penting. Payload seperti `1 OR 1=1` akan berhenti sebagai parameter URL/UUID yang tidak valid, bukan menjadi bagian dari query SQL.
- Kami tidak membuat query SQL manual untuk alur login, appointment, invoice, prescription, dan rekam medis. Query dibangun lewat ORM agar parameter binding ditangani oleh Django.
- Untuk environment lokal, SQLite digunakan melalui backend Django. Pada deployment database server terpisah, kami menyiapkan prinsip least privilege dengan akun database khusus aplikasi yang hanya memiliki izin sesuai kebutuhan runtime.

Django ORM dipakai sebagai lapisan utama akses database karena ORM melakukan parameter binding dan membangun query melalui API terstruktur. Dengan cara ini, karakter seperti tanda kutip, operator boolean, atau potongan SQL tidak berubah menjadi instruksi database baru. Validasi tipe seperti UUID juga membantu menolak payload sejak tahap routing/form validation, sehingga request berbahaya berhenti sebelum menyentuh query bisnis.

Least privilege pada user database tetap dicatat karena SQL Injection tidak hanya dicegah dari sisi query. Bila suatu hari ada query yang salah, dampaknya lebih kecil jika user database aplikasi tidak punya hak administratif seperti membuat, menghapus, atau mengubah struktur tabel di luar kebutuhan runtime.

* **Code Snippet Perbandingan:**

Tidak secure:

```python
username = request.POST["username"]
password = request.POST["password"]

query = (
    "SELECT * FROM auth_app_useraccount "
    f"WHERE username = '{username}' AND password = '{password}'"
)
user = UserAccount.objects.raw(query)
```

Secure, diambil dari `auth_app/views.py`:

```python
username = form.cleaned_data["username"]
user_obj = UserAccount.objects.get(username=username)
user = authenticate(request, username=username, password=password)
```

Tidak secure:

```python
patient_id = request.GET["patient_id"]
status = request.GET["status"]

query = (
    "SELECT * FROM billing_app_invoice "
    f"WHERE patient_id = '{patient_id}' AND status = '{status}'"
)
invoices = Invoice.objects.raw(query)
```

Secure, diambil dari `core_app/views.py`:

```python
invoices = (
    Invoice.objects.filter(
        encounter__patient=patient,
        status__in=[Invoice.InvoiceStatus.UNPAID, Invoice.InvoiceStatus.PAID],
    )
    .select_related("encounter")
    .order_by("-createdAt")
)
```

### 2. Code Injection dan XSS

* **Penjelasan Vulnerability:**

Code Injection terjadi ketika input user diproses sebagai kode atau ditampilkan sebagai HTML/script aktif. Rubrik menyebut Code Injection, tetapi test case yang digunakan lebih dekat ke Stored/Reflected XSS dan HTML Injection. Karena itu, bagian ini menghubungkan dua risiko tersebut: eksekusi kode dari input dan rendering HTML/script yang tidak aman. Kerentanan ini terkait dengan CWE-94, Improper Control of Generation of Code, dan CWE-79, Improper Neutralization of Input During Web Page Generation.

Test case yang dicakup:

- `TC-CI-01`: payload `<script>alert(...)</script>` tidak dieksekusi di browser.
- `TC-CI-02`: tag HTML dari input tidak dirender sebagai markup aktif.
- `TC-CI-03`: validasi/sanitasi input berjalan di backend, bukan hanya di frontend.

* **Teknik Mitigasi:**

- Kami memakai template Django dengan auto escaping default untuk menampilkan data dari user sebagai teks biasa.
- Kami tidak menambahkan bypass escaping seperti `mark_safe()` atau filter `|safe` pada field yang berasal dari input pengguna.
- Kami membuat allowlist karakter pada form registrasi pasien untuk nama, alamat, dan nomor telepon.
- Kami memberi batas panjang eksplisit pada field form, misalnya `max_length` pada form login, resep, appointment, dan rekam medis.
- Kami menjalankan validasi password bawaan Django pada registrasi pasien.

Auto escaping Django membuat karakter seperti `<`, `>`, dan `"` ditampilkan sebagai teks biasa, sehingga payload script tidak berubah menjadi elemen HTML aktif. Validasi backend dengan allowlist dipakai pada field yang seharusnya punya format jelas, misalnya nama, alamat, nomor telepon, dan alasan appointment. Alasannya sederhana: browser atau frontend bisa dimanipulasi, sedangkan backend adalah titik terakhir yang menentukan data boleh masuk ke sistem atau tidak.

Batas panjang field juga membantu mengurangi ruang payload dan menjaga data tetap sesuai konteks domain. Untuk field medis yang memang membutuhkan teks bebas, data tetap diproses sebagai teks dan ditampilkan melalui template escaping Django.

* **Code Snippet Perbandingan:**

Tidak secure:

```python
def self_register(request):
    if request.method == "POST":
        full_name = request.POST["full_name"]

        patient = Patient.objects.create(
            name=full_name,
            address=request.POST["address"],
            phoneNumber=request.POST["phone_number"],
        )

        return redirect("auth_app:login")
```

Secure, diambil dari `core_app/forms.py`:

```python
PROFILE_NAME_REGEX = re.compile(r"^[A-Za-z0-9 .,'-]+$")

def clean_full_name(self):
    value = self.cleaned_data["full_name"].strip()
    if not PROFILE_NAME_REGEX.fullmatch(value):
        raise ValidationError("Nama hanya boleh berisi huruf, angka, spasi, dan tanda baca dasar.")
    return value
```

### 3. Broken Authentication

* **Penjelasan Vulnerability:**

Broken Authentication terjadi ketika proses login, penyimpanan password, pembatasan percobaan login, session, atau role access tidak dijaga dengan baik. Dampaknya user tidak sah dapat mencoba masuk, mempertahankan session lama, atau mengakses fitur yang bukan haknya. Kerentanan ini terkait dengan CWE-287, Improper Authentication; CWE-307, Improper Restriction of Excessive Authentication Attempts; CWE-613, Insufficient Session Expiration; dan CWE-862, Missing Authorization.

Test case yang dicakup:

- `TC-BA-01`: password tersimpan dalam bentuk hash Django, bukan plaintext.
- `TC-BA-02`: akun terkunci setelah 5 kali login gagal.
- `TC-BA-03`: logout menghapus session server-side dan endpoint terlindungi menolak akses tanpa session valid.

* **Teknik Mitigasi:**

- Kami mewariskan model user dari `AbstractUser`, sehingga password dibuat melalui `create_user()` dan disimpan memakai password hasher Django.
- Kami memakai `authenticate()` dari Django untuk proses login, bukan membandingkan password secara manual.
- Kami menambahkan field `failedLoginAttempts` dan `lockedUntil` untuk menyimpan status percobaan login gagal.
- Kami mengunci akun selama 15 menit setelah 5 kali kegagalan login.
- Kami membedakan staff internal dan pasien eksternal lewat `mfaEnabled` dan `is_patient`.
- Kami memakai `django.contrib.auth.logout()` untuk logout dan membatasi endpoint logout agar hanya menerima `POST`.
- Kami mengatur session agar berakhir saat browser ditutup dan memiliki umur 30 menit melalui `SESSION_COOKIE_AGE = 1800`.
- Kami menerapkan RBAC dengan `login_required`, `user_passes_test`, dan decorator `staff_role_required`.

Password hashing bawaan Django dipakai karena format hash Django menyertakan algoritma, salt, dan iterasi. Bila database terbaca pihak tidak berwenang, password asli tidak langsung tersedia. `authenticate()` juga menjaga proses verifikasi tetap berada pada mekanisme resmi Django, bukan perbandingan manual.

Lockout setelah 5 kegagalan membatasi brute force dan credential stuffing. Timeout 15 menit memberi jeda yang cukup untuk memperlambat serangan, tetapi tetap memungkinkan user sah kembali mencoba tanpa intervensi admin permanen. Session invalidation saat logout dan batas umur session mengurangi risiko token lama dipakai ulang. RBAC dipakai karena autentikasi hanya menjawab "siapa user ini", sedangkan authorization menjawab "fitur apa yang boleh diakses user ini".

* **Code Snippet Perbandingan:**

Tidak secure:

```python
user = UserAccount.objects.get(username=request.POST["username"])

if user.password == request.POST["password"]:
    request.session["user_id"] = str(user.id)
    return redirect("auth_app:profile")
```

Secure, diambil dari `auth_app/views.py`:

```python
user = authenticate(request, username=username, password=password)

if user is None:
    user_obj.failedLoginAttempts += 1

    if user_obj.failedLoginAttempts >= 5:
        user_obj.lock_account(minutes=15)
    else:
        user_obj.save(update_fields=["failedLoginAttempts"])
```

Tidak secure:

```python
def staff_role_required(*allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
```

Secure, diambil dari `auth_app/decorators.py`:

```python
def staff_role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required.")

            try:
                staff = request.user.staff
            except Staff.DoesNotExist:
                return HttpResponseForbidden("Staff account required.")

            if staff.role not in allowed_roles:
                return HttpResponseForbidden("Access denied.")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
```

Tidak secure:

```python
@login_required
def create_prescription(request, encounter_id):
    ...
```

Secure, contoh pemakaian dari `pharmacy_app/views.py`:

```python
@login_required
@staff_role_required("DOCTOR")
def create_prescription(request, encounter_id):
    ...
```

### 4. CSRF

* **Penjelasan Vulnerability:**

CSRF terjadi ketika situs eksternal memaksa browser user yang sedang login untuk mengirim request write ke aplikasi tanpa persetujuan user. Dalam sistem rumah sakit, risiko ini dapat menyentuh aksi seperti membuat appointment, memproses pembayaran, atau mengubah data yang seharusnya hanya dilakukan lewat form resmi aplikasi. Kerentanan ini terkait dengan CWE-352, Cross-Site Request Forgery.

Test case yang dicakup:

- `TC-CSRF-01`: seluruh form yang melakukan operasi write memiliki token CSRF.
- `TC-CSRF-02`: request tanpa token atau dengan token tidak valid ditolak oleh server.
- `TC-CSRF-03`: cross-origin request tidak diberi akses bebas.

* **Teknik Mitigasi:**

- Kami mengaktifkan `django.middleware.csrf.CsrfViewMiddleware` di `MIDDLEWARE`.
- Kami menaruh `{% csrf_token %}` pada form POST di template login, logout, registrasi pasien, appointment, rekam medis, resep, validasi resep, dispensing, dan pembayaran.
- Kami memberi `@csrf_protect` pada `login_view`.
- Kami memberi `@require_POST` pada `logout_view`, sehingga logout hanya berjalan melalui form POST yang membawa token CSRF.
- Kami menjalankan aplikasi sebagai aplikasi same-origin Django dan tidak membuka konfigurasi CORS permisif.

CSRF token membuat request write harus membawa nilai rahasia yang dibuat oleh server dan terikat pada sesi/origin yang sah. Situs eksternal dapat mencoba mengirim form POST, tetapi tidak dapat membaca token dari halaman aplikasi karena dibatasi same-origin policy browser. Verifikasi di middleware memastikan perlindungan terjadi di server, bukan hanya berdasarkan tampilan form.

Untuk kebutuhan produksi atau API yang akan diakses dari domain berbeda, CORS perlu dibuat eksplisit dengan allowlist origin yang dipercaya. Alasannya, konfigurasi CORS yang terlalu longgar dapat membuat browser mengizinkan origin luar membaca response atau mengirim request lintas domain dengan pola yang tidak sesuai desain aplikasi.

* **Code Snippet Perbandingan:**

Tidak secure:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
```

Secure, diambil dari `progjut_hospital_system/settings.py`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
```

Tidak secure:

```python
def login_view(request):
    ...

def logout_view(request):
    logout(request)
    return redirect("auth_app:login")
```

Secure, diambil dari `auth_app/views.py`:

```python
@csrf_protect
def login_view(request):
    ...

@require_POST
def logout_view(request):
    logout(request)
    return redirect("auth_app:login")
```

Tidak secure:

```html
<form method="post" class="login-form" novalidate>
    {{ form.as_p }}
    <button type="submit" class="btn-primary">Sign In</button>
</form>
```

Secure, diambil dari `auth_app/templates/auth_app/login.html`:

```html
<form method="post" class="login-form" novalidate>
    {% csrf_token %}
    {{ form.as_p }}
    <button type="submit" class="btn-primary">Sign In</button>
</form>
```

## C. Checklist Test Case Secure Coding

### SQL Injection

| ID | Skenario | Ekspektasi | Bukti yang Dicatat |
| --- | --- | --- | --- |
| TC-SQLi-01 | Login memakai payload `admin' OR '1'='1` | Login gagal dan tidak ada bypass autentikasi | Screenshot pesan gagal login |
| TC-SQLi-02 | Payload `UNION SELECT` pada input pencarian/filter/form | Data user lain tidak terekstrak | Screenshot hasil request dan database tetap normal |
| TC-SQLi-03 | Payload SQL pada parameter ID, misalnya `/medical/records/1 OR 1=1/` | Request ditolak/404 dan query tidak dieksekusi sebagai SQL | Screenshot response 404 atau hasil test |

### Code Injection dan XSS

| ID | Skenario | Ekspektasi | Bukti yang Dicatat |
| --- | --- | --- | --- |
| TC-CI-01 | Input `<script>alert(1)</script>` pada field yang menerima teks | Script tidak berjalan di browser | Screenshot halaman setelah submit |
| TC-CI-02 | Input tag HTML seperti `<b>Injected</b>` | Tag tampil sebagai teks biasa atau ditolak form | Screenshot output/validation error |
| TC-CI-03 | Payload karakter tidak sesuai allowlist di registrasi pasien | Backend menolak input dan data tidak tersimpan | Screenshot error "Nama hanya boleh..." |

### Broken Authentication

| ID | Skenario | Ekspektasi | Bukti yang Dicatat |
| --- | --- | --- | --- |
| TC-BA-01 | Cek password user di database | Password tersimpan sebagai hash Django, bukan plaintext | Screenshot database/admin/shell |
| TC-BA-02 | Login gagal 5 kali berturut-turut | Akun terkunci selama 15 menit | Screenshot pesan akun terkunci |
| TC-BA-03 | Logout lalu akses endpoint protected | User diarahkan ke login atau menerima 403 | Screenshot setelah akses ulang endpoint |

### CSRF

| ID | Skenario | Ekspektasi | Bukti yang Dicatat |
| --- | --- | --- | --- |
| TC-CSRF-01 | Inspect form POST | Ada hidden input `csrfmiddlewaretoken` | Screenshot inspect element |
| TC-CSRF-02 | Kirim POST tanpa token memakai Postman/curl | Server mengembalikan HTTP 403 | Screenshot response 403 |
| TC-CSRF-03 | Uji request dari origin tidak terdaftar | Tidak ada akses cross-origin bebas; aplikasi berjalan same-origin | Screenshot header/response pengujian |

## D. TODO Screenshot

- [ ] Screenshot halaman login normal.
- [ ] Screenshot login gagal dengan payload SQL Injection untuk `TC-SQLi-01`.
- [ ] Screenshot payload `UNION SELECT` atau payload SQL lain yang tidak mengekstrak data untuk `TC-SQLi-02`.
- [ ] Screenshot request parameter ID tidak valid yang menghasilkan 404 untuk `TC-SQLi-03`.
- [ ] Screenshot input `<script>alert(1)</script>` yang tidak dieksekusi untuk `TC-CI-01`.
- [ ] Screenshot payload HTML yang tampil sebagai teks atau ditolak form untuk `TC-CI-02`.
- [ ] Screenshot validasi allowlist backend pada registrasi pasien untuk `TC-CI-03`.
- [ ] Screenshot password user di database/shell yang berbentuk hash untuk `TC-BA-01`.
- [ ] Screenshot akun terkunci setelah 5 kali gagal login untuk `TC-BA-02`.
- [ ] Screenshot akses endpoint protected setelah logout untuk `TC-BA-03`.
- [ ] Screenshot inspect element form POST yang menunjukkan `csrfmiddlewaretoken` untuk `TC-CSRF-01`.
- [ ] Screenshot request POST tanpa CSRF token yang menghasilkan HTTP 403 untuk `TC-CSRF-02`.
- [ ] Screenshot pengujian cross-origin/same-origin policy untuk `TC-CSRF-03`.
- [ ] Screenshot dashboard masing-masing role: patient, doctor, pharmacist, cashier.
- [ ] Screenshot halaman access denied/403 saat role mencoba membuka endpoint yang bukan haknya.

## E. Catatan Verifikasi Lokal

Test otomatis yang relevan dapat dijalankan dengan:

```bash
python manage.py test
```

Beberapa test yang mendukung rubrik:

- `auth_app.tests.AuthSecurityTests.test_account_locked_after_five_failed_attempts`
- `auth_app.tests.AuthSecurityTests.test_locked_account_cannot_login_even_with_correct_password`
- `core_app.tests.PatientPortalTests.test_self_registration_rejects_script_payload`
- `core_app.tests.PatientPortalTests.test_patient_cannot_access_other_patient_encounter`
- `medical_app.tests.MedicalSecurityTests.test_invalid_uuid_payload_does_not_execute_sql_injection`
- `medical_app.tests.MedicalSecurityTests.test_medical_record_is_stored_encrypted`

## F. Link Video Demo

**Link Video:** TODO
