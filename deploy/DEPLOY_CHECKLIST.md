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
| `.env` | `MEDIAMTX_WHIP_URL`, `MEDIAMTX_WHEP_URL` | alamat publik MediaMTX yang harus bisa dijangkau browser HP teknisi di lapangan |
| `.env` | `WEBRTC_ICE_SERVERS` (isi kredensial TURN) | dipakai sisi Django/browser saat bikin koneksi WebRTC |
| `deploy/mediamtx.generated.yml` | `webrtcICEServers2` → `password:` TURN | **harus sama persis** dengan `WEBRTC_ICE_SERVERS` di atas & config coturn |
| `deploy/mediamtx.generated.yml` | `webrtcAllowOrigin` | ganti dari `"*"` ke domain FASOP produksi |
| `deploy/mediamtx.generated.yml` | `webrtcEncryption` + cert/key | wajib TLS di produksi — browser HP blokir akses kamera (`getUserMedia`) di halaman non-HTTPS |
| `deploy/mediamtx.generated.yml` | `authHTTPAddress`, `runOnRecordSegmentComplete` | ganti dari `127.0.0.1:8000` kalau MediaMTX **bukan** di server yang sama dengan Django/gunicorn |
| coturn (server terpisah, di luar repo ini) | realm, kredensial TURN | infrastruktur baru — belum ada sama sekali di repo ini, perlu disiapkan sendiri |
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
