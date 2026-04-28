# FASOP — Sistem Manajemen Aset & Monitoring Sistem Tenaga

Aplikasi web internal PT. PLN (Persero) UIP3B Sulawesi untuk manajemen aset peralatan telekomunikasi & SCADA, pencatatan pemeliharaan, monitoring gangguan, serta monitoring sistem tenaga secara real-time.

---

## Fitur

### OPSIS — Monitoring Sistem Tenaga (Real-time)
- Dashboard live: beban kit total (MW), frekuensi sistem (Hz), data per pembangkit
- Chart beban harian (00:00–sekarang) dengan tanda puncak siang (12:00) & malam (18:30)
- Chart frekuensi 30 menit terakhir (data per detik)
- Chart komposisi pembangkit per jenis (PLTA / PLTU / PLTD / PLTG / PLTGU)
- Halaman detail per pembangkit (trend MW/MVAR 1–24 jam)
- Rangkuman historis: kemarin / 7 hari / 30 hari — beban puncak, rata-rata, durasi abnormal frekuensi
- Ekspor Excel: data frekuensi & beban per hari
- Sumber data: MSSQL (SCADA real-time) → fallback ke PostgreSQL (data yang dikumpulkan tiap menit)
- Monitoring RTU: status UP/DOWN per RTU dari MSSQL

### Manajemen Perangkat
- Inventaris perangkat per jenis: Router, Switch, MUX, PLC, Radio, VoIP, Rectifier, RTU, SAS, RoIP, UPS, Genset, Teleproteksi
- Grouping kelompok: Telekomunikasi, SCADA, Proteksi Sistem
- Upload foto & eviden perangkat
- QR Code per perangkat — halaman publik tanpa login
- Peta jaringan & distribusi per lokasi

### Fiber Optic
- Inventaris segmen kabel FO (ADSS / OPGW / Drop)
- Detail per-core: status, fungsi, koneksi A/B, data OTDR
- QR Code per segmen — halaman publik menampilkan pemakaian core & status

### Pemeliharaan
- Form pemeliharaan preventif per jenis perangkat (detail teknis lengkap)
- Pemeliharaan korektif terkait gangguan
- Berita Acara (BA) Pemasangan, Pembongkaran, Penggantian
- Workflow tanda tangan digital: Draft → Minta TTD Engineer → TTD AM
- Ekspor PDF dengan tanda tangan & eviden foto
- Approval oleh Asisten Manager

### Gangguan
- Pencatatan tiket gangguan peralatan & link fiber optic
- Tracking status: Open → In Progress → Resolved → Closed
- Log perubahan & riwayat penanganan
- Halaman publik status gangguan via token

### Dashboard & Monitoring
- Statistik pemeliharaan & gangguan bulanan (Chart.js)
- Health Index peralatan
- Distribusi status per jenis & per kelompok peralatan
- Jadwal pemeliharaan

### Gudang
- Manajemen alat uji & spare part
- Mutasi stok

### Keamanan
- Login rate limiting: kunci akun otomatis setelah 5x gagal (django-axes)
- URL obfuskasi: integer ID di-encode dengan Hashids
- Session & CSRF cookie: HttpOnly, SameSite=Lax, Secure (HTTPS)
- Role-based access: Viewer, Operator, Teknisi, Asisten Manager
- Single session per user
- Tanda tangan digital tersimpan di profil user

---

## Tech Stack

| Layer | Teknologi |
|---|---|
| Backend | Django 6.0 · Python 3.12+ |
| Database Utama | PostgreSQL (prod) · SQLite (dev) |
| Database SCADA | Microsoft SQL Server (MSSQL) via pyodbc |
| Frontend | Bootstrap 5 · Bootstrap Icons · Chart.js 4 |
| Font | DM Sans · JetBrains Mono (Google Fonts) |
| PDF | ReportLab · WeasyPrint |
| Excel | openpyxl |
| Server | Nginx + Gunicorn |
| Keamanan | django-axes · Hashids |

---

## Instalasi Lokal

```bash
git clone https://github.com/binusK2/fasop.git
cd fasop

pip install -r requirements.txt

# Install ODBC Driver 17 for SQL Server (untuk koneksi MSSQL/OPSIS)
# Ubuntu/Debian: https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server

cp .env.example .env
# Edit .env sesuai kebutuhan

python manage.py migrate
python manage.py runserver
```

### Isi `.env`

```env
SECRET_KEY=your-secret-key-yang-kuat
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

# Database PostgreSQL (prod — untuk SnapLive, SnapFreq OPSIS)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fasop
DB_USER=fasop
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# MSSQL — Sumber data real-time SCADA (opsional, fallback ke PostgreSQL)
MSSQL_HOST=192.168.x.x,1433
MSSQL_DB=nama_database
MSSQL_USER=username
MSSQL_PASS=password
MSSQL_TABLE=dbo.HIS_MEAS_KIT
MSSQL_RT_TABLE=dbo.KIT_REALTIME
MSSQL_FREQ_TABLE=dbo.SYS_FREQ_HIS
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

# API Key untuk integrasi eksternal
API_KEY=
```

---

## Struktur Aplikasi

```
fasop/
├── api/            # REST API (integrasi n8n / Google Sheets)
├── devices/        # Manajemen perangkat, FO, dashboard
├── maintenance/    # Pemeliharaan preventif, korektif, Berita Acara
├── gangguan/       # Tiket gangguan
├── health_index/   # Kalkulasi Health Index peralatan
├── inspection/     # Inservice inspection
├── jadwal/         # Jadwal pemeliharaan
├── gudang/         # Alat uji & spare part
├── notifikasi/     # Notifikasi in-app
├── opsis/          # Monitoring sistem tenaga real-time (OPSIS)
│   └── management/commands/
│       ├── collect_live.py   # Kumpulkan MW/MVAR per menit → SnapLive
│       └── collect_freq.py   # Kumpulkan Hz per detik → SnapFreq
├── device_mon/     # Monitoring status RTU
├── fasop/          # Settings, URL root, konverter Hashids
├── static/         # CSS, JS, gambar statis
├── media/          # Upload foto, tanda tangan (tidak di-git)
└── manage.py
```

---

## OPSIS — Data Collection

OPSIS menyimpan data historis ke PostgreSQL menggunakan dua management command yang dijalankan sebagai cron job:

```bash
# Jalankan tiap menit — ambil MW/MVAR semua pembangkit dari MSSQL → simpan ke SnapLive
python manage.py collect_live

# Jalankan tiap menit — ambil data Hz per detik dari MSSQL → simpan ke SnapFreq
python manage.py collect_freq
```

Contoh crontab:
```cron
* * * * * /path/to/venv/bin/python /path/to/fasop/manage.py collect_live
* * * * * /path/to/venv/bin/python /path/to/fasop/manage.py collect_freq
```

Jika MSSQL tidak reachable, dashboard otomatis fallback ke data PostgreSQL (SnapLive/SnapFreq) yang terakhir dikumpulkan.

---

## Deployment

```bash
git pull origin main
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart gunicorn
sudo systemctl reload nginx
```

### Unlock akun yang terkunci (django-axes)
```bash
# Via Django admin: /secure-panel/ → Axes → Access Attempts → hapus record
# Via shell:
python manage.py axes_reset_user --username namauser
```

---

> File `.env`, `db.sqlite3`, `media/`, dan `venv/` tidak di-track git.
