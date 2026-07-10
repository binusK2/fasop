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
| File | Yang diisi | Kenapa manual |
|---|---|---|
| coturn (server terpisah, di luar repo ini) | install + realm + kredensial TURN | infrastruktur baru — belum ada sama sekali di repo ini, perlu dicek/disiapkan sendiri (lihat "Kenapa TURN penting" di bawah) |
| `.env` | `WEBRTC_ICE_SERVERS` (isi kredensial TURN) | dipakai sisi Django/browser saat bikin koneksi WebRTC |
| `deploy/mediamtx.generated.yml` | `webrtcICEServers2` → `password:` TURN | **harus sama persis** dengan `WEBRTC_ICE_SERVERS` di atas & config coturn |
| DNS + sertifikat (mis. certbot) | subdomain baru khusus MediaMTX, mis. `media.domain-anda` | dibutuhkan kalau pakai jalur TLS via nginx (opsi B di `deploy/mediamtx.yml`, lihat baris berikutnya) |
| nginx | `deploy/nginx-mediamtx.conf.example` → copy ke `sites-available/`, isi `server_name` & path cert, `nginx -t && systemctl reload nginx` | reverse-proxy TLS ke MediaMTX pakai domain+cert yang **sudah ada** — cara termudah kalau nginx+cert untuk Django sudah jalan (tidak perlu urus cert terpisah untuk MediaMTX) |
| `.env` | `MEDIAMTX_WHIP_URL`, `MEDIAMTX_WHEP_URL` | isi `https://media.domain-anda` (domain subdomain MediaMTX di atas), bukan `localhost` |
| `deploy/mediamtx.generated.yml` | `webrtcAllowOrigin` | isi origin **Django FASOP** (mis. `https://fasop.domain-anda`) — beda dengan domain MediaMTX-nya sendiri |
| `deploy/mediamtx.generated.yml` | `authHTTPAddress`, `runOnRecordSegmentComplete` | ganti dari `127.0.0.1:8000` **hanya kalau** MediaMTX di server **terpisah** dari Django/gunicorn |
| Firewall server | buka port TCP 8889 (kalau tidak lewat nginx), UDP 8189 (`webrtcICEUDPMuxAddress`), UDP 3478 (TURN) | tanpa ini WebRTC gagal connect meski semua config sudah benar |
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
