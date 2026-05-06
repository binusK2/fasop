# SOP Update Aplikasi FASOP

**Berlaku untuk:** Developer / Tim IT UIP3B Sulawesi  
**Terakhir diperbarui:** April 2026

---

## Gambaran Alur

```
Permintaan Update
      │
      ▼
1. Buat Branch Baru (dari main)
      │
      ▼
2. Kerjakan di Lokal (kode, test)
      │
      ▼
3. Commit & Push ke GitHub
      │
      ▼
4. Buat Pull Request → Review
      │
      ▼
5. Merge ke main
      │
      ▼
6. Deploy ke Server Produksi
      │
      ▼
7. Verifikasi di Browser
```

---

## Persiapan Awal (Sekali Saja)

### Prasyarat di komputer lokal
- Python 3.12+
- Git
- ODBC Driver 17 for SQL Server (jika perlu tes koneksi MSSQL)
- Akses ke repository GitHub: `github.com/binusK2/fasop`

### Clone & setup lokal
```bash
git clone https://github.com/binusK2/fasop.git
cd fasop

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — minimal: SECRET_KEY, DEBUG=True, ALLOWED_HOSTS=localhost
# Untuk tes OPSIS: isi juga MSSQL_HOST, MSSQL_DB, dst.

python manage.py migrate
python manage.py runserver
# Buka http://localhost:8000
```

---

## Langkah-Langkah Update

### 1. Pastikan main Terbaru

Sebelum mulai, selalu ambil versi terbaru dari main:

```bash
git checkout main
git pull origin main
```

---

### 2. Buat Branch Baru

Nama branch mencerminkan isi perubahan:

```bash
# Format: feat/<nama-fitur>  atau  fix/<nama-bug>  atau  docs/<deskripsi>
git checkout -b feat/tambah-laporan-bulanan
git checkout -b fix/tooltip-chart-beban
git checkout -b docs/update-readme
```

> **Jangan langsung kerja di branch `main`.** Semua perubahan harus lewat branch terpisah.

---

### 3. Kerjakan Perubahan

Kerjakan kode di branch tersebut. Panduan per jenis perubahan:

#### Tambah fitur baru (view, halaman, model)
```
opsis/
├── models.py       ← jika ada model baru
├── views.py        ← tambah view function
├── urls.py         ← daftarkan URL baru
└── templates/opsis/
    └── halaman_baru.html
```

Jika ada model baru atau perubahan model:
```bash
python manage.py makemigrations
python manage.py migrate
```

#### Ubah tampilan (template HTML / CSS)
- Edit file di `opsis/templates/opsis/` atau `templates/`
- Refresh browser — tidak perlu restart server untuk template

#### Ubah logika backend (views.py, models.py)
- Edit file, simpan
- Django development server auto-reload

#### Tambah dependensi Python baru
```bash
pip install nama-paket
pip freeze > requirements.txt   # ← WAJIB diperbarui
git add requirements.txt
```

---

### 4. Test di Lokal

Sebelum commit, pastikan:

- [ ] Halaman yang diubah terbuka tanpa error (cek browser console)
- [ ] Fitur baru berjalan sesuai yang diharapkan
- [ ] Halaman lain yang tidak diubah tidak ikut rusak (cek dashboard, OPSIS, dll.)
- [ ] Tidak ada error di terminal Django (`python manage.py runserver`)
- [ ] Jika ada migrasi: `python manage.py migrate` berhasil

---

### 5. Commit

Simpan perubahan dengan pesan commit yang jelas:

```bash
git add nama_file.py                    # tambah file yang diubah
git add opsis/templates/opsis/          # atau folder
git add -p                              # atau review per-hunk

git commit -m "feat(opsis): tambah laporan beban bulanan PDF"
```

**Format pesan commit:**

| Prefix | Kapan Dipakai |
|---|---|
| `feat(modul):` | Fitur baru |
| `fix(modul):` | Perbaikan bug |
| `docs:` | Perubahan dokumentasi saja |
| `style(modul):` | Perubahan tampilan/CSS saja |
| `refactor(modul):` | Refactor kode tanpa ubah perilaku |
| `chore:` | Perubahan konfigurasi, dependensi |

Contoh modul: `opsis`, `devices`, `maintenance`, `gangguan`, `gudang`

---

### 6. Push ke GitHub

```bash
git push -u origin feat/tambah-laporan-bulanan
```

---

### 7. Buat Pull Request (PR)

1. Buka `github.com/binusK2/fasop`
2. Klik tombol **"Compare & pull request"** yang muncul
3. Isi:
   - **Judul**: ringkas apa yang berubah
   - **Deskripsi**: jelaskan kenapa perubahan ini diperlukan, apa yang diubah, cara test
4. Klik **"Create pull request"**
5. Minta review ke anggota tim lain (jika ada)

---

### 8. Merge ke `main`

Setelah review selesai dan tidak ada masalah:

1. Klik **"Merge pull request"** di GitHub
2. Klik **"Confirm merge"**
3. Branch bisa dihapus setelah merge (klik "Delete branch")

---

### 9. Deploy ke Server Produksi

Login ke server, lalu jalankan:

```bash
cd /path/to/fasop                   # sesuaikan path di server

# Ambil perubahan terbaru dari main
git pull origin main

# Install dependensi baru (jika ada)
pip install -r requirements.txt

# Jalankan migrasi database (jika ada model baru)
python manage.py migrate

# Kumpulkan static files (jika ada perubahan CSS/JS/gambar)
python manage.py collectstatic --noinput

# Restart aplikasi
sudo systemctl restart gunicorn
sudo systemctl reload nginx
```

> **Catatan:** `collectstatic` hanya perlu dijalankan jika ada perubahan di folder `static/`.  
> Perubahan template HTML tidak perlu collectstatic — langsung aktif setelah restart gunicorn.

---

### 10. Verifikasi

Buka aplikasi di browser dan pastikan:

- [ ] Halaman utama & OPSIS dashboard terbuka normal
- [ ] Fitur yang baru di-update bekerja sesuai harapan
- [ ] Tidak ada error 500 di halaman manapun
- [ ] Cek log server jika ada indikasi masalah:
  ```bash
  sudo journalctl -u gunicorn -n 50 --no-pager
  ```

---

## Jenis Perubahan Umum

### Hanya ubah teks / tampilan HTML
```
Langkah: 3 → 4 → 5 → 6 → 7 → 8 → 9 (tanpa migrate & collectstatic)
```

### Tambah halaman / fitur baru
```
Langkah: 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 (dengan migrate jika ada model baru)
```

### Perbaiki bug
```
Langkah: 1 (checkout main) → 2 (branch fix/) → 3 → 4 → 5 → 6 → 7 → 8 → 9
```

### Perubahan darurat di produksi (hotfix)
```
Langkah: 1 (checkout main) → 2 (branch hotfix/) → 3 → 5 → 6 → 7 → 8 → 9
```
> Hotfix tetap harus lewat PR, tidak boleh langsung push ke main.

---

## Hal yang TIDAK Boleh Dilakukan

| Larangan | Alasannya |
|---|---|
| `git push origin main` langsung | Bypass review — risiko bug masuk produksi tanpa dicek |
| Edit file langsung di server produksi | Tidak tercatat di git, hilang saat pull berikutnya |
| Commit file `.env` | Berisi password/secret — berbahaya jika tersebar |
| Commit folder `media/` atau `venv/` | File besar, sudah ada di `.gitignore` |
| `python manage.py migrate --fake` tanpa alasan jelas | Bisa merusak konsistensi skema database |

---

## OPSIS — Hal Khusus

### Menambah pembangkit baru
1. Masuk ke Django Admin (`/secure-panel/`)
2. Buka **Opsis → Pembangkits** → Add
3. Isi kode KIT (harus sama persis dengan kolom `KIT` di MSSQL `KIT_REALTIME`)
4. Tidak perlu deploy ulang — langsung aktif

### Cron job `collect_live` & `collect_freq`
- Berjalan otomatis tiap menit di server (crontab)
- Jika data OPSIS tidak update, cek:
  ```bash
  crontab -l                              # pastikan cron aktif
  python manage.py collect_live           # jalankan manual untuk cek error
  python manage.py collect_freq
  ```

### Jika MSSQL tidak terhubung
- Dashboard otomatis fallback ke data PostgreSQL terakhir
- Tidak perlu tindakan khusus — data historis tetap tampil

---

## Kontak & Eskalasi

| Masalah | Langkah |
|---|---|
| Error 500 setelah deploy | Cek log gunicorn → rollback dengan `git revert` jika perlu |
| Database corrupt / migrasi gagal | Jangan paksa — hubungi pengelola database |
| MSSQL tidak terhubung | Cek jaringan ke server SCADA, cek kredensial di `.env` |
| Akun terkunci (login gagal 5x) | `python manage.py axes_reset_user --username namauser` |

---

> Dokumen ini disimpan di `SOP_UPDATE.md` di root repository.  
> Update dokumen ini setiap kali ada perubahan signifikan pada alur kerja.
