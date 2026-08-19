# Isolasi Worker OPSIS (mencegah MSSQL down = seluruh FASOP down)

## Kenapa

`opsis/views.py` adalah **satu-satunya** kode yang query MSSQL langsung per
request web (semua app lain — device_mon, up2bmakassar, logsheet — baca
dari PostgreSQL yang disinkronkan cron, lihat CLAUDE.md). Kalau MSSQL
lambat/macet, request ke `/opsis/*` bisa menahan worker gunicorn cukup
lama. Dengan satu pool gunicorn tunggal untuk seluruh FASOP, cukup banyak
request `/opsis/*` bersamaan (mis. dashboard OPSIS yang di-poll banyak
browser tiap 1-5 detik) untuk menghabiskan SEMUA worker — akibatnya
`/inspection/` (dipakai operator gardu induk), dashboard, dan semua rute
lain ikut kena gateway timeout walau tidak menyentuh MSSQL sama sekali.

Fix di kode (`opsis/mssql.py` circuit breaker, sudah live) mengurangi
DURASI setiap request yang gagal. Panduan ini menambah lapisan kedua:
memisahkan **pool proses** gunicorn, supaya walau OPSIS penuh, pool utama
tidak ikut kehabisan worker. Satu codebase, satu database, satu domain —
cuma dua proses gunicorn di belakang nginx.

## Ringkasan arsitektur

```
                                   ┌─ pool utama (fasop.service, TIDAK berubah) ─┐
                                   │  semua rute KECUALI /opsis/*                │
nginx (satu domain, satu server) ─┤                                             │
                                   └─ pool OPSIS (fasop-opsis.service, BARU)  ───┘
                                      hanya /opsis/*, worker-class gthread
```

Kedua pool menjalankan **kode yang persis sama** (`fasop.wsgi:application`
dari working directory yang sama) — cuma proses gunicorn terpisah dengan
bind port berbeda. Session/login/cookie tetap satu (satu domain, satu
`SECRET_KEY`), jadi user tidak akan "ke-logout" saat pindah antar rute.

## Yang dibutuhkan sebelum mulai

1. **Isi service systemd fasop yang SUDAH ADA** — `User=`, `Group=`,
   `WorkingDirectory=`, path venv persis. Samakan tiga field itu di
   `deploy/gunicorn-opsis.service.example` sebelum dipasang.
2. **Cek port 8002 belum dipakai**: `ss -tlnp | grep 8002` — kalau bentrok,
   ganti port di kedua file (`.service` dan nginx) ke port lain yang bebas.
3. **Lokasi file nginx server block FASOP** yang sedang aktif (mis.
   `/etc/nginx/sites-available/fasop`) — kita cuma MENAMBAH, bukan mengganti
   file ini.

## Langkah pemasangan (didesain supaya tidak ada downtime di tengah proses)

### 1. Pasang & jalankan pool OPSIS BARU — belum menyentuh nginx sama sekali

```bash
sudo cp deploy/gunicorn-opsis.service.example /etc/systemd/system/fasop-opsis.service
sudo nano /etc/systemd/system/fasop-opsis.service   # sesuaikan User/Group/WorkingDirectory/path venv

sudo systemctl daemon-reload
sudo systemctl start fasop-opsis
sudo systemctl status fasop-opsis          # pastikan "active (running)", tidak crash-loop
```

### 2. Verifikasi pool baru bisa jawab request — TANPA lewat nginx dulu

```bash
curl -i http://127.0.0.1:8002/opsis/
```

Yang diharapkan: HTTP 302 redirect ke `/login/` (karena `@login_required`,
belum ada session) — ini bukti Django benar-benar jalan di pool baru.
Kalau connection refused / error lain, **stop di sini**, jangan lanjut ke
nginx — perbaiki dulu (`journalctl -u fasop-opsis -n 50`).

Aman diulang berkali-kali — situs production **belum terpengaruh sama
sekali** sampai langkah ini selesai, karena nginx belum tahu pool ini ada.

### 3. Backup config nginx yang aktif

```bash
sudo cp /etc/nginx/sites-available/fasop /etc/nginx/sites-available/fasop.bak-$(date +%Y%m%d)
```

Simpan ini — kalau langkah 4-5 bermasalah, tinggal copy balik file `.bak`
ini lalu `nginx -t && systemctl reload nginx` untuk rollback instan.

### 4. Tambahkan upstream + location block

Edit file server block FASOP yang aktif (`/etc/nginx/sites-available/fasop`
atau namanya masing-masing), tempel isi
`deploy/nginx-opsis-pool.conf.example` — blok `upstream` di level `http`
(luar `server {}`), blok `location /opsis/` di dalam `server {}` yang
sudah ada.

### 5. WAJIB test config sebelum reload — ini yang mencegah downtime

```bash
sudo nginx -t
```

Kalau ada error sintaks, **JANGAN reload** — perbaiki dulu sampai
`nginx -t` bilang "syntax is ok" dan "test is successful". `nginx -t`
tidak mengubah apa pun yang sedang berjalan, jadi aman dicoba berkali-kali.

### 6. Reload (BUKAN restart) nginx

```bash
sudo systemctl reload nginx
```

`reload` graceful — nginx membaca config baru, buka worker baru dengan
config itu, baru pelan-pelan mematikan worker lama SETELAH request yang
sedang berjalan selesai. Tidak ada koneksi yang diputus paksa (beda dengan
`restart`, yang benar-benar mematikan lalu menyalakan ulang — hindari,
walau cuma sekejap ada celah tidak ada listener).

### 7. Verifikasi end-to-end

```bash
curl -I https://fasop.domain-anda/opsis/      # harus tetap 302 ke login, sekarang lewat nginx+pool baru
curl -I https://fasop.domain-anda/            # dashboard utama tidak terganggu
curl -I https://fasop.domain-anda/inspection/ # rute operator gardu induk tidak terganggu
```

Buka juga di browser: `/opsis/`, `/`, `/inspection/`, `/device-mon/` — pastikan
semua normal, login masih tersimpan (session sama, jadi seharusnya tidak
perlu login ulang).

### 8. Aktifkan pool OPSIS saat boot

```bash
sudo systemctl enable fasop-opsis
```

## Rollback

Kapan pun setelah langkah 4, kalau ada yang aneh:

```bash
sudo cp /etc/nginx/sites-available/fasop.bak-YYYYMMDD /etc/nginx/sites-available/fasop
sudo nginx -t && sudo systemctl reload nginx
```

Ini mengembalikan nginx ke kondisi SEBELUM ada pool OPSIS — semua request
(termasuk `/opsis/*`) kembali ke pool utama seperti semula. Pool
`fasop-opsis.service` boleh dibiarkan jalan (tidak dipakai nginx, tidak
berdampak) atau dimatikan: `sudo systemctl stop fasop-opsis`.

## Setelah terpasang — tuning

Amati beban nyata beberapa hari (`journalctl -u fasop-opsis -f`,
`htop`/`ps` untuk lihat pemakaian memori 2 proses × N thread). Naikkan
`--workers`/`--threads` di `fasop-opsis.service` kalau masih terlihat
antrian saat MSSQL lambat — restart service (bukan reload, ini gunicorn-nya
sendiri) setelah ubah:

```bash
sudo systemctl restart fasop-opsis
```

(`restart` di sini aman karena yang berdampak cuma pool OPSIS-nya sendiri,
bukan seluruh nginx/FASOP.)
