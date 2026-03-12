# FASOP — Asset & Pemeliharaan Peralatan

Aplikasi web untuk manajemen aset peralatan telekomunikasi dan pencatatan pemeliharaan (preventive & corrective).

---

## Fitur
- 📋 Manajemen perangkat (Router, Switch, MUX, PLC, Radio, VoIP, Rectifier)
- 🔧 Form pemeliharaan per jenis perangkat dengan detail teknis
- 📊 Laporan & ekspor PDF pemeliharaan
- 📍 Manajemen lokasi / site
- 🖼️ Upload foto perangkat & pemeliharaan
- 🔐 Manajemen user (Admin, Asisten Manager, Teknisi)
- ✍️ Tanda tangan digital teknisi
- 📱 Responsive UI (Bootstrap 5)

---

## Tech Stack
- **Backend:** Django 6.x · Python 3.12+
- **Database:** SQLite (development) / PostgreSQL (production)
- **Frontend:** Bootstrap 5 · Bootstrap Icons
- **Server:** Nginx + Gunicorn (VPS)

---

## Instalasi Lokal

```bash
# Clone repo
git clone https://github.com/binusK2/fasop.git
cd fasop

# Install dependencies
pip install -r requirements.txt

# Buat file .env
cp .env.example .env
# Edit .env sesuai kebutuhan

# Migrasi database
python manage.py migrate

# Jalankan server
python manage.py runserver
```

### Isi `.env`
```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## Struktur Folder
```
fasop/
├── devices/        # App manajemen perangkat
├── maintenance/    # App pemeliharaan
├── fasop/          # Settings package Django
├── media/          # Upload foto
├── static/         # Static files
└── manage.py
```

---

## Deployment (VPS)
```bash
git pull origin main
python manage.py migrate
sudo systemctl restart gunicorn
sudo systemctl reload nginx
```

---

> File `.env`, `db.sqlite3`, `media/`, dan `venv/` tidak di-track git.
