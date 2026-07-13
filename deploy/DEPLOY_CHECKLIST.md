# Live Streaming — Checklist Deploy

Daftar semua file yang tersentuh saat menyalakan fitur Live Streaming di
server produksi, dan mana yang sudah dibantu otomatis. Jalankan dulu:

```bash
bash deploy/setup_streaming.sh
```

Aman dijalankan berulang kali — jalankan lagi kapan pun ragu apakah setup
sudah lengkap, tidak akan menimpa yang sudah benar.

## Otomatis oleh `setup_streaming.sh`

- [ ] `.env` → `MEDIAMTX_AUTH_SECRET` (di-generate acak kalau belum ada)
- [ ] `.env` → `STREAMING_RECORDINGS_ROOT` (default `<repo>/streaming_recordings` kalau belum diisi)
- [ ] Direktori rekaman dibuat
- [ ] `deploy/mediamtx.generated.yml` di-render dari `deploy/mediamtx.yml` (secret & path rekaman sudah terisi — file ini **jangan pernah di-commit**, sudah masuk `.gitignore`)
- [ ] Cron `purge_old_recordings` terpasang (harian 03:00)

## HARUS diisi manual — tidak bisa diotomasi dari repo ini

| File | Yang diisi | Kenapa manual |
|---|---|---|
| coturn | `apt install coturn`, lalu `deploy/turnserver.conf.example` → copy ke `/etc/turnserver.conf`, isi `realm`/password, `systemctl enable --now coturn` | infrastruktur baru — belum ada sama sekali di server, perlu diinstall (lihat "Kenapa TURN penting" di bawah) |
| `.env` | `WEBRTC_ICE_SERVERS` (isi kredensial TURN) | dipakai sisi Django/browser saat bikin koneksi WebRTC |
| `deploy/mediamtx.generated.yml` | `webrtcICEServers2` → `password:` TURN | **harus sama persis** dengan `WEBRTC_ICE_SERVERS` di atas & config coturn |
| DNS | subdomain baru khusus MediaMTX, mis. `media.domain-anda` → A record ke IP publik server | dibutuhkan kalau pakai jalur TLS via nginx (opsi B di `deploy/mediamtx.yml`, lihat baris berikutnya) |
| nginx + certbot | **urutan penting**: (1) pasang `deploy/nginx-mediamtx-temp.conf.example` dulu (port 80 saja, tanpa SSL) → `nginx -t && systemctl reload nginx`; (2) `sudo certbot --nginx -d media.domain-anda` — certbot otomatis tambah blok SSL ke file yang sama. **Jangan** langsung pasang `deploy/nginx-mediamtx.conf.example` — file itu referensi cert yang belum ada sebelum certbot jalan, `nginx -t` akan gagal | reverse-proxy TLS ke MediaMTX pakai domain+cert yang **sudah ada** — cara termudah kalau nginx untuk Django sudah jalan (tidak perlu urus cert terpisah untuk MediaMTX) |
| `.env` | `MEDIAMTX_WHIP_URL`, `MEDIAMTX_WHEP_URL` | isi `https://media.domain-anda` (domain subdomain MediaMTX di atas), bukan `localhost` |
| `deploy/mediamtx.generated.yml` | `webrtcAllowOrigins` | isi origin **Django FASOP** (mis. `https://fasop.domain-anda`) — beda dengan domain MediaMTX-nya sendiri |
| `deploy/mediamtx.generated.yml` | `authHTTPAddress`, `runOnRecordSegmentComplete` | ganti dari `127.0.0.1:8000` **hanya kalau** MediaMTX di server **terpisah** dari Django/gunicorn |
| Firewall server | buka port TCP 8889 (kalau tidak lewat nginx), UDP 8189 (`webrtcLocalUDPAddress`), UDP 3478 (TURN) | tanpa ini WebRTC gagal connect meski semua config sudah benar |
| `deploy/mediamtx.service` | `User`, `Group`, `WorkingDirectory`, `ExecStart` | lalu `sudo systemctl enable --now mediamtx` |

## Kenapa TURN penting (jangan di-skip)

HP teknisi di lapangan hampir selalu di belakang CGNAT operator seluler.
Tanpa TURN yang valid, koneksi WebRTC akan gagal connect dari jaringan
seluler meskipun semua yang lain sudah benar — ini bukan bug kode, tapi
prasyarat infrastruktur yang memang belum dikerjakan di sesi ini.

## Yang TIDAK perlu disentuh lagi

- Migrasi Django (`streaming/migrations/`) — jalan otomatis lewat
  `manage.py migrate` seperti biasa, tidak ada langkah tambahan.
- `deploy/mediamtx.yml` — ini **template**, jangan diedit langsung untuk
  isi secret. Edit lewat `setup_streaming.sh` supaya hasil generate-nya
  (`mediamtx.generated.yml`) yang benar-benar dipakai MediaMTX.
