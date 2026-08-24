# Arsip Excel Hasil Inspeksi Harian

Setiap hari **jam 12.00** server menulis satu file Excel berisi hasil inspeksi
hari itu ke share Windows `\\192.168.77.5\fasop\inspeksi harian`:

```
\\192.168.77.5\fasop\inspeksi harian\2026-08\Inspeksi_Harian_2026-08-24.xlsx
```

Isinya sama persis dengan tombol **Export Excel** di halaman
*Hasil Inspeksi Harian* (`/inspection/harian/`) — keduanya memakai
`inspection/laporan.py::workbook_harian()`, jadi kolomnya tidak mungkin
berbeda antara yang dilihat di layar dan yang diarsipkan.

Isi file: sheet **Ringkasan** (per jenis peralatan: total, terinspeksi, belum,
normal, alarm, diflag, %) + satu sheet per jenis peralatan dengan kolom sesuai
peralatannya masing-masing (Catu Daya berisi kolom rectifier/baterai, DFR
berisi kolom DFR, Server ADS berisi kolom Server ADS, dst).

---

## 1. Mount share-nya dulu (Linux)

Django menulis ke **path biasa**, ia tidak berbicara SMB sendiri. Jadi share
Windows itu harus di-mount lebih dulu. Sekali saja, sebagai root:

```bash
sudo apt install cifs-utils
sudo mkdir -p /mnt/fasop

# Kredensial disimpan terpisah supaya tidak ikut di /etc/fstab yang world-readable
sudo tee /etc/fasop-smb.cred >/dev/null <<'EOF'
username=<user share>
password=<password share>
domain=<DOMAIN atau nama komputer>
EOF
sudo chmod 600 /etc/fasop-smb.cred

# uid/gid = user yang menjalankan gunicorn/cron FASOP
sudo tee -a /etc/fstab >/dev/null <<'EOF'
//192.168.77.5/fasop  /mnt/fasop  cifs  credentials=/etc/fasop-smb.cred,uid=fasop,gid=fasop,file_mode=0664,dir_mode=0775,vers=3.0,nofail,_netdev  0  0
EOF

sudo mount -a
ls -l /mnt/fasop
```

`nofail` penting: kalau NAS-nya sedang mati, server tetap boot normal.

Kalau versi SMB-nya ditolak, coba `vers=2.1` atau `vers=1.0` sesuai umur mesin
192.168.77.5.

## 2. Isi `.env`

```env
INSPEKSI_EXPORT_DIR="/mnt/fasop/inspeksi harian"
```

Folder `inspeksi harian` dan subfolder bulanannya dibuat otomatis oleh command
kalau belum ada — yang harus sudah ada cuma mount-nya.

Lalu `sudo systemctl restart gunicorn` (agar settings terbaca ulang).

## 3. Pasang cron

```bash
bash deploy/setup_inspeksi_export_cron.sh
```

Terpasang: `0 12 * * *  manage.py export_inspeksi_harian --days 2`

`--days 2` menulis ulang hari ini **dan** kemarin. Kalau satu hari cronnya
gagal (NAS lepas, server mati), hari berikutnya otomatis menyusul — tidak perlu
backfill manual. File hari yang sama ditimpa, bukan ditambah.

Jadwal lain, mis. dua kali sehari:

```bash
bash deploy/setup_inspeksi_export_cron.sh "0 12,17 * * *"
```

## 4. Uji tanpa menulis file

```bash
python manage.py export_inspeksi_harian --dry-run
python manage.py export_inspeksi_harian --tanggal 2026-08-20            # satu hari tertentu
python manage.py export_inspeksi_harian --days 7                        # tulis ulang seminggu terakhir
python manage.py export_inspeksi_harian --dir /tmp/uji                  # tujuan lain, tanpa .env
```

---

## Kalau file tidak muncul di share

Urutan yang biasanya menjawab:

1. `tail -n 50 logs/export_inspeksi_harian.log` — pesan errornya ada di sana,
   command mengembalikan exit code ≠ 0 kalau ada hari yang gagal.
2. `mount | grep fasop` — share-nya masih ter-mount? CIFS bisa lepas diam-diam
   setelah NAS reboot; `sudo mount -a` memasangnya lagi.
3. `sudo -u fasop touch "/mnt/fasop/inspeksi harian/uji.txt"` — hak tulisnya
   benar? `uid=`/`gid=` di fstab harus user yang menjalankan cron FASOP, bukan
   root.
4. `python manage.py export_inspeksi_harian --dry-run` — memastikan
   `INSPEKSI_EXPORT_DIR` benar-benar terbaca dari `.env`.

File `.Inspeksi_Harian_*.xlsx.tmp` yang tertinggal artinya penulisan terputus
di tengah (share lepas saat menulis) — aman dihapus, isi finalnya baru diberi
nama sebenarnya setelah tertulis penuh.
