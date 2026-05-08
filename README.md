# PKPL26_HospitalSys - Hospital Information System

Repositori ini berisi implementasi Tugas 3 - Kelompok untuk mata kuliah Pengantar Keamanan Perangkat Lunak, berfokus pada Praktik Secure Coding menggunakan framework Django.

---

## 🚀 Petunjuk Instalasi & Menjalankan Aplikasi Secara Lokal

Ikuti langkah-langkah berikut untuk melakukan setup proyek di mesin lokal Anda:

1. **Clone Repositori**
    ```
    git clone https://gitlab.cs.ui.ac.id/pkpl26/30-progjut-my-beloved/pkpl26_30_progjut-my-beloved.git

    cd PKPL26_HospitalSys
    ```

2. **Buat & Aktivasi Virtual Environment**
   * Windows:

     ```
     python -m venv venv
     venv\Scripts\activate
     ```
   * macOS/Linux:
     ```
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies**
    ```
    pip install -r requirements.txt
    ```

4. **Setup Environment Variables (.env)**
   Buat file bernama .env di direktori utama (sejajar dengan manage.py) dan isi dengan konfigurasi berikut:
    ```
    DJANGO_SECRET_KEY=isi_dengan_secret_key_lokal_anda
    ```

5. **Jalankan Migrasi Database**

    ```
    python manage.py makemigrations
    python manage.py migrate
    ```

6. **Jalankan Server Lokal**
    ```
    python manage.py runserver
    ```
   Akses aplikasi di browser melalui http://127.0.0.1:8000/

---

## A. Deskripsi Aplikasi

> TODO: ...

* **Skenario:** Hospital Information System
* **Fitur Utama:** Rekam medis pasien, jadwal dokter, resep obat.
* **Peran Pengguna:** Dokter, Pasien, Apoteker, Petugas Pendaftaran, Kasir.
* **Stack Teknologi:** Django, SQLite, Python.

---

## B. Implementasi Secure Coding

> TODO: ...

### 1. Code Injection Prevention

* **Penjelasan Vulnerability:** 
Code Injection terjadi ketika app mengeksekusi kode yang berasal dari input user tanpa validasi. Attacker bisa inject kode yang berbahaya (Python, SQL, template expression) untuk merusak aplikasi.

* **Code Snippet Perbandingan:** [TODO: Snippet kode sebelum (vulnerable) dan sesudah (secure) sebagai perbandingan]
* **Teknik Mitigasi:** [TODO: Penjelasan teknik mitigasi yang digunakan]

### 2. Broken Authentication Mitigation

* **Penjelasan Vulnerability:** 
Broken Authentication memungkinkan attacker untuk mendapatkan akses tanpa kredensial yang sah. Ini termasuk:
- Password disimpan plaintext atau hash lemah
- Session token yang predictable atau tidak di-invalidate
- Tidak ada rate limiting pada login attempts
- Tidak ada pembedaan privilege antar role

* **Code Snippet Perbandingan:** [TODO: Snippet kode sebelum (vulnerable) dan sesudah (secure) sebagai perbandingan]
* **Teknik Mitigasi:** [TODO: Penjelasan teknik mitigasi yang digunakan]

### 3. CSRF Protection

* **Penjelasan Vulnerability:** 
CSRF attack memungkinkan attacker mengirim request yang tidak sah atas nama user yang authenticated. Contoh: user login ke bank, kemudian mengklik link jahat yang melakukan transfer dana tanpa persetujuan.

* **Code Snippet Perbandingan:** [TODO: Snippet kode sebelum (vulnerable) dan sesudah (secure) sebagai perbandingan]
* **Teknik Mitigasi:** [TODO: Penjelasan teknik mitigasi yang digunakan]

### 4. SQL Injection Prevention

* **Penjelasan Vulnerability:** 
SQL Injection terjadi ketika user input digunakan langsung dalam SQL query tanpa sanitasi. Attacker bisa memanipulasi query untuk mengakses/mengubah/menghapus data tanpa authorization.

* **Code Snippet Perbandingan:** [TODO: Snippet kode sebelum (vulnerable) dan sesudah (secure) sebagai perbandingan]
* **Teknik Mitigasi:** [TODO: Penjelasan teknik mitigasi yang digunakan]

---

## C. Screenshot Aplikasi

> TODO: Tampilkan screenshot antarmuka utama dan fitur keamanan.

* [TODO: Screenshot Halaman Login (Menunjukkan mitigasi Broken Auth)]
* [TODO: Screenshot Halaman Utama (Role-Based Access)]
* [TODO: Screenshot Halaman Form (Menunjukkan implementasi keamanan input)]

---

## D. Hasil Test-Case

> TODO: Masukin screenshot atau log hasil pengujian test-case.

* [TODO: Hasil Test Case 1 - Code Injection]
* [TODO: Hasil Test Case 2 - Broken Authentication]
* [TODO: Hasil Test Case 3 - CSRF]
* [TODO: Hasil Test Case 4 - SQL Injection]

---

## 🎥 Link Video Demo & Penjelasan

> TODO: Masukin link video presentasi/demo yang telah diupload ke youtube.

* **Link Video:** 