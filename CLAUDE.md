# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FASOP** is a production Django 6.0 web application for PT. PLN (Persero) UIP3B Sulawesi. It manages telecommunications and SCADA equipment assets, preventive/corrective maintenance workflows, fault tickets, and real-time power system monitoring (OPSIS).

Tech stack: Django 6.0 + Python 3.12, PostgreSQL (primary), MSSQL via pyodbc (SCADA historian), Bootstrap 5, Chart.js 4 — no Node.js/npm build step.

Live Streaming (`streaming/` app) additionally depends on external, non-pip infrastructure — not installed by `pip install -r requirements.txt`, see "Live Streaming — External Infrastructure" below: **MediaMTX** (media server binary), **coturn** (TURN/STUN server), **ffmpeg** (server-side recording transcode), and (in the FASOP production deployment) **Cloudflare Tunnel** (`cloudflared`) to expose MediaMTX's WebRTC endpoint.

---

## Common Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in values
python manage.py migrate
python manage.py runserver

# After model changes
python manage.py makemigrations
python manage.py migrate

# After static file changes (production)
python manage.py collectstatic --noinput

# OPSIS data collection (normally run as cron, every minute)
python manage.py collect_live   # MW/MVAR from MSSQL → SnapLive
python manage.py collect_freq   # Hz/second from MSSQL → SnapFreq

# Unlock an axes-locked user account
python manage.py axes_reset_user --username <username>

# Run Django tests
python manage.py test

# Production restart
sudo systemctl restart gunicorn && sudo systemctl reload nginx
```

---

## Architecture

### App Structure

Each of the 15 `INSTALLED_APPS` Django apps follows a standard layout (`models.py`, `views.py`, `forms.py`, `urls.py`, `templates/<app>/`). Key apps:

| App | Responsibility |
|---|---|
| `devices/` | Core asset inventory (Device, FiberOptic, SiteLocation), dashboard, wiring diagram editor, device audit trail (DeviceLog/DeviceEvent), single-session + login auditing (`signals.py`) |
| `maintenance/` | Preventive/corrective maintenance, Berita Acara (BA), digital signature workflow, PDF export (WeasyPrint, `pdf_weasy.py`) |
| `gangguan/` | Fault ticket CRUD, status workflow, public status page (token-based, no login) |
| `opsis/` | Real-time power monitoring dashboard, MSSQL historian, data collection cron commands; EWS Defense Scheme (`/opsis/ews/`) — margin nilai ukur realtime terhadap ambang setting rele, peralatan & pemetaan tabel/kolom MSSQL-nya didaftarkan dari Admin (lihat "OPSIS — EWS Defense Scheme") |
| `health_index/` | Equipment health scoring (0–100), computed (not stored) from 9 weighted factors |
| `inspection/` | Inservice inspection for Operator role, plus the daily-results page (`/inspection/harian/`) and its Excel archive — column schema per equipment type lives in `inspection/laporan.py` |
| `gudang/` | Warehouse / spare parts inventory; stock level is computed from `MutasiSparepart`, not a stored field |
| `device_mon/` | Realtime equipment status monitoring — RTU UP/DOWN via MSSQL (`collect_rtu` cron) at `/device-mon/`, plus Zabbix host status at `/device-mon/zabbix/`: pull periodically via Zabbix API (`zabbix_api.py`, cron `sync_zabbix`) + push realtime via webhook (`/device-mon/zabbix/webhook/`, token `ZABBIX_WEBHOOK_TOKEN`); `ZabbixHost` optionally linked to `devices.Device`; WhatsApp blast is **opt-in per host** from Admin (`wa_alert` + `wa_min_severity` threshold) — see "Early Warning WhatsApp" below; full setup in `deploy/ZABBIX_INTEGRATION.md`. Both sources live in one app deliberately — "realtime equipment status" belongs together regardless of data source |
| `scada_av/` | SCADA/RTU availability and RCD success rate; wraps the `spectrum7_av/` calculation library |
| `notifikasi/` | In-app notification center (per-user + broadcast); other apps push notifications via `notif_ke_user()` / `notif_ke_am()` helpers |
| `jadwal/` | Monthly preventive-maintenance visit scheduling per location, with HI/age/device-count priority ranking |
| `common_enemy/` | Cross-cutting multi-site issue tickets (SCADA/telkom/prosis), auto-numbered `CE-YYYYMM-XXXX` |
| `dokumentasi/` | Relay setting & wiring-diagram document repository with uploader→checker approval workflow |
| `auditlog/` | Custom (not django-auditlog) superuser audit log; entries are created by explicit `log_action()` calls in views, not signals |
| `streaming/` | Field maintenance live streaming (WebRTC WHIP/WHEP via MediaMTX, `deploy/mediamtx.yml`); Teknisi broadcasts, Teknisi/AM view, only AM can join as Pengawas for 2-way talkback; teknisi's video is recorded (server-side ffmpeg transcode, see below) and pengawas's talkback audio is recorded as a **separate** clip (`LiveSession.talkback_recording_path`) rather than mixed into one file; recordings kept 7 days (`purge_old_recordings` cron) |
| `up2bmakassar/` | Kinerja SCADATEL (`/kinerja-scadatel/`) — availability harian titik Telemetering/Telesignal, log RC, dan SOE log, dibaca **read-only** dari OFDB (`dbup2bmakasar` di MSSQL, `ofdb.py`); lihat "Kinerja SCADATEL — OFDB" di bawah |
| `api/` | REST API for n8n / Google Sheets integrations (no models — not in `INSTALLED_APPS`, but `urls.py` is still wired into `fasop/urls.py` at `/api/v1/`) |
| `fasop/` | Root settings, URL routing, Hashids helper, URL converters |

`spectrum7_av/` is a custom (in-house, not vendored) SCADA availability calculation library — RTU/RCD/SOE metrics from OFDB historian exports. It is not a Django app and isn't in `INSTALLED_APPS`; only `scada_av/calculator.py` imports it.

All app URLs are included in `fasop/urls.py`. Django Admin is at `/secure-panel/`.

### URL ID Obfuscation (Hashids)

Integer PKs are **never** exposed in URLs directly. They are encoded with Hashids using `SECRET_KEY` as the salt.

```python
from fasop.hashids_helper import encode, decode

hid = encode(pk)      # int → 6+ char string for URLs
pk  = decode(hid)     # string → int (returns None if invalid)
```

The `HashIdConverter` (`fasop/converters.py`) is registered as the `hid` URL type:
```python
path('device/<hid:hid>/', views.device_detail, name='device_detail')
```

Always use `encode()`/`decode()` when building or reading URLs that contain PKs.

### Two-Database Architecture

- **PostgreSQL** — primary database for all application data plus collected OPSIS snapshots (`SnapLive`, `SnapFreq`).
- **MSSQL** — read-only SCADA historian (`opsis/mssql.py`). Never write to MSSQL.

MSSQL connection is established per-request in `opsis/mssql.py` with a TCP reachability pre-check (`_tcp_ping()`) before querying. If `MSSQL_HOST` is unset, or the host is unreachable, the relevant function (e.g. `get_live_data()`) returns dummy/empty data instead of raising — there is no generic fallback-to-PostgreSQL query path, each function degrades independently.

### Middleware Stack (order matters)

```
SecurityMiddleware → SessionMiddleware → CommonMiddleware → CsrfViewMiddleware
→ AuthenticationMiddleware → AxesMiddleware → MessageMiddleware
→ XFrameOptionsMiddleware
→ ForcePasswordChangeMiddleware   # force new password on first login
→ OpsisMaintenanceMiddleware      # /opsis/* → halaman pemeliharaan bila sakelarnya aktif
→ OpsisAccessMiddleware           # restricts opsis role to /opsis/ only
→ OperatorAccessMiddleware        # restricts operator role to /inspection/ only
→ DispatcherAccessMiddleware      # restricts dispatcher role to telecom testing
→ SingleSessionMiddleware         # one active session per user (except Operator)
```

All custom middleware lives in `devices/middleware.py`.

### Role-Based Access

Roles are stored in `UserProfile` (ForeignKey to User). Middleware enforces route-level restrictions; view-level checks use decorators from `devices/permissions.py`.

| Role | Access scope |
|---|---|
| Superuser | Everything |
| Teknisi | Create/edit devices and maintenance |
| Asisten Manager (AM) | Approve maintenance, manage locations |
| Viewer | Read-only |
| Operator | `/inspection/` only; shared session allowed |
| Opsis | `/opsis/` only |
| Dispatcher | Telecom testing only |

### Maintenance Signature Workflow

`Maintenance` objects follow a status machine: **Draft → Diminta TTD → TTD Teknisi → Selesai (AM Approved)**. Digital signatures (PNG, stored in `UserProfile`) are embedded into PDF exports via ReportLab/WeasyPrint (`maintenance/pdf_weasy.py`).

`BeritaAcaraRecord` (BA) is a related but separate workflow under the same app: covers `pemasangan`/`pembongkaran`/`penggantian`/`gangguan`/`penormalan`/`lainnya` field reports, with its own TTD pair (`ttd_pa_*`, `ttd_technician_*`) and optional photo evidence (`BeritaAcaraEviden`). A BA can either be generated as a PDF from structured `rows_data` (JSONField), or attached directly as a finished document via `file_upload` (skip PDF generation entirely — see `maintenance/views.py::ba_upload`). `nomor_ba` is manually entered and checked for uniqueness, not auto-numbered like the IDs below.

### Cross-Cutting Patterns

- **Auto-numbered IDs** — several apps generate monthly-reset sequence numbers in `save()`/a `generate_nomor_*()` helper instead of using the PK: `gangguan.Gangguan.nomor_gangguan` (`GNG-YYYYMM-XXXX`), `common_enemy.CommonEnemy.nomor_ce` (`CE-YYYYMM-XXXX`), `dokumentasi.SettingRele`/`GambarDevice` (`SR-`/`GR-YYYYMM-XXXX`). Follow this pattern for any new document/ticket model rather than inventing a new scheme.
- **Computed-not-stored metrics** — health score (`health_index/calculator.py`, 9 weighted factors via `registry.py`), warehouse stock (`gudang.Sparepart` — `stok_sekarang` derives from summing `MutasiSparepart.masuk`/`keluar`), and SCADA availability (`scada_av` — float 0–1, computed offline per session) are all properties/calculators, not editable model fields. Periodic snapshots (`HISnapshot`, `SnapLive`, `SnapFreq`) persist point-in-time values for history/trend charts.
- **Notification fan-out** — to notify users from any app, call `notifikasi.views.notif_ke_user()` / `notif_ke_am()` rather than creating `Notifikasi` rows directly; `user=None` broadcasts to everyone (`Q(user=user) | Q(user__isnull=True)` scoping).
- **Device-level audit trail vs. global audit log are different systems** — `devices.DeviceLog` (per-field diffs, auto on device edit) and `devices.signals.py` (login/logout + single-session enforcement) are separate from the `auditlog` app, which only gets entries when a view explicitly calls `auditlog.utils.log_action()`. Don't assume one implies the other when adding a new mutating view.
- **Uploader → checker approval workflow** — `dokumentasi.SettingRele` (`draft → on_check → uptodate`/`perlu_perbaikan`) is the reference implementation if a similar review/approval flow is needed elsewhere; permission is `created_by == request.user` (uploader) vs `checker == request.user` (reviewer), both bypassed for superuser.

### Management Commands

| Command | App | Purpose |
|---|---|---|
| `collect_live` | opsis | Cron, every minute — MW/MVAR from MSSQL → `SnapLive` |
| `collect_freq` | opsis | Cron, every minute — Hz from MSSQL → `SnapFreq` |
| `collect_trafo` | opsis | Cron, every minute — P/Q per distribution transformer from MSSQL `ALL_TRANS_DATA` → `SnapTrafo`; powers the 24h per-transformer chart (`/opsis/beban-trafo-chart/`), since `ALL_TRANS_DATA` itself has no history; supports `--dry-run` |
| `collect_rtu` | device_mon | Cron, every minute — RTU UP/DOWN from MSSQL `RTU_ALL_STATE` → `RTU`/`RTULog`; supports `--dry-run` |
| `generate_rename_plan` | devices | One-off — builds a device-rename plan for review before applying |
| `apply_rename_plan` | devices | One-off — applies a previously generated rename plan |
| `audit_device_names` | devices | One-off — reports naming inconsistencies across `Device` |
| `fix_notif_urls` | notifikasi | One-off — repairs malformed notification links |
| `purge_old_recordings` | streaming | Cron, daily — deletes `LiveSession` recording files past `STREAMING_RECORDING_RETENTION_DAYS` (default 7 days since `ended_at`); supports `--dry-run` |
| `sync_kinerja_analog` | up2bmakassar | Cron, daily ~01:00 — availability harian titik TELEMETERING dari OFDB → `KinerjaAnalogHarian`; `--date`, `--days` (backfill), `--dry-run` |
| `sync_kinerja_digital` | up2bmakassar | Cron, daily ~01:00 — sama untuk titik digital; `--jenis TELESIGNAL` (default) / `RTU` / `MASTER` / `TELEKOMUNIKASI` / `ALL` |
| `sync_rc` | up2bmakassar | Cron, daily — log RC dari OFDB `scd_his_rc` + hasilnya di-resolve dari `scd_his_message` → `RemoteControl` |
| `arsip_titik_kinerja` | up2bmakassar | Arsipkan daftar titik `kinerja=1` dari OFDB ke CSV — jalankan sebelum apa pun diubah di 19.1 |
| `daftar_station` | up2bmakassar | Daftar station (PATH1) di data kinerja + status aktif/nonaktifnya, untuk dicocokkan dengan daftar station UP2B |
| `cek_kinerja_ofdb` | up2bmakassar | Diagnosa read-only — koneksi OFDB, induk point type yang ketemu, jumlah titik per jenis, lama query harian, dan jumlah baris tersimpan |
| `export_inspeksi_harian` | inspection | Cron, harian 12.00 — tulis laporan Excel hasil inspeksi hari itu ke `INSPEKSI_EXPORT_DIR` (`<dir>/<YYYY-MM>/Inspeksi_Harian_<tgl>.xlsx`); `--tanggal`, `--days` (tulis ulang N hari terakhir), `--dir`, `--dry-run` |
| `sync_zabbix` | device_mon | Cron, every 2-5 min — pull host/problem status via Zabbix API (JSON-RPC) → `ZabbixHost`/`ZabbixEventLog`; complements the `/device-mon/zabbix/webhook/` push path; supports `--dry-run` |
| `collect_freq_rt` | opsis | Cron tiap menit — Hz dari MSSQL `SYS_FREQ_RT` → `SnapFreqRT`; pakai `--loop --interval 1 --durasi 55` (1 sampel/detik) lewat `deploy/setup_freq_rt_cron.sh`, lihat "Riwayat Frekuensi (dua sumber)" |
| `cek_armada_kit` | opsis | Diagnosa read-only — bandingkan armada KIT di `KIT_REALTIME`, `HIS_MEAS_KIT`, `Pembangkit`, dan `RESPON_PLANTS`; jalankan sebelum menyimpulkan selisih MW |
| `probe_tabel_ews` | opsis | Diagnosa read-only — daftar kolom + baris contoh sebuah tabel MSSQL, untuk memetakan `TitikEWS.sumber_*` |
| `seed_ews` | opsis | One-off, idempotent — isi kolom & 93 titik EWS Defense Scheme dari berkas DS UP2B Makassar 2026 (tanpa pemetaan MSSQL); `--dry-run`, `--perbarui` |

---

## Coding Conventions

### Models
- Timestamps: `created_at = DateTimeField(auto_now_add=True)`, `updated_at = DateTimeField(auto_now=True)`
- User tracking: `created_by = ForeignKey(User, ...)`, `deleted_by = ForeignKey(User, ...)`
- Soft deletes: `is_deleted = BooleanField(default=False)` — never hard-delete device records
- Flexible specs: `spesifikasi = JSONField()` for device-type-specific technical data (schema defined in `devices/device_schema.py`)

### Views
- All application views are **function-based** with `@login_required` and role decorators
- Class-based views are only used for Django Admin customization
- Filter state is preserved in `request.session` (e.g., device list filters)
- Paginator is used for all long lists

### Commit Messages
Follow the format from `SOP_UPDATE.md`:
```
feat(module): description
fix(module): description
docs: description
style(module): description
refactor(module): description
chore: description
```
Modules: `opsis`, `devices`, `maintenance`, `gangguan`, `gudang`, `inspection`, `health_index`, `notifikasi`, `jadwal`, `common_enemy`, `dokumentasi`, `scada_av`, `device_mon`, `auditlog`, `api`, etc.

### Branching
- Never push directly to `main`
- Branch naming: `feat/<name>`, `fix/<name>`, `hotfix/<name>`, `docs/<name>`
- All changes go through a PR

---

## Environment Variables

Configured via `.env` (parsed by `python-decouple`):

```env
SECRET_KEY=           # Required — also used as Hashids salt
DEBUG=True/False
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

# Primary database (PostgreSQL for prod, SQLite for local dev)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=fasop
DB_USER=fasop
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# MSSQL SCADA historian (optional — OPSIS returns dummy/empty data if absent or unreachable)
MSSQL_HOST=192.168.x.x,1433
MSSQL_DB=
MSSQL_USER=
MSSQL_PASS=
MSSQL_TABLE=dbo.HIS_MEAS_KIT
MSSQL_RT_TABLE=dbo.KIT_REALTIME
MSSQL_FREQ_TABLE=dbo.SYS_FREQ_HIS
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

API_KEY=              # For /api/v1/ integrations

# Early Warning WhatsApp (OpenWA gateway) — see "Early Warning WhatsApp" below
WA_ALERT_ENABLED=False        # master switch; False = no WhatsApp notifications at all
WA_API_BASE=http://localhost:2785
WA_API_KEY=                   # X-API-Key of the OpenWA gateway
WA_SESSION_ID=                # WhatsApp session id in OpenWA
WA_CHAT_IDS=                  # RTU Early Warning targets (groups end in @g.us, comma-separated)
WA_CHAT_IDS_INSPECTION=       # inspection alarm targets; empty = not sent
WA_CHAT_IDS_ZABBIX=           # Zabbix host blast targets; empty = falls back to WA_CHAT_IDS
WA_TIMEOUT=10

# Zabbix Integration (device_mon app) — see deploy/ZABBIX_INTEGRATION.md for full setup
# Sumber prediksi beban OPSIS — 'sheet' (default, spreadsheet via n8n) | 'ml'
OPSIS_FORECAST_SOURCE=sheet

# Arsip Excel hasil inspeksi harian (cron export_inspeksi_harian jam 12.00).
# Path biasa — share Windows harus sudah di-mount; lihat deploy/EXPORT_INSPEKSI_HARIAN.md
INSPEKSI_EXPORT_DIR="/mnt/fasop/inspeksi harian"   # kosong = cron export dimatikan
# Zabbix Integration (zabbix_mon app) — see deploy/ZABBIX_INTEGRATION.md for full setup
ZABBIX_API_URL=               # e.g. http://zabbix.domain/api_jsonrpc.php
ZABBIX_API_TOKEN=             # preferred auth (Zabbix >= 5.4, Administration > API tokens)
ZABBIX_API_USER=              # fallback auth (username/password) if no API token
ZABBIX_API_PASSWORD=
ZABBIX_API_TIMEOUT=10
ZABBIX_HOST_GROUPS=           # optional, comma-separated — empty = all hosts
ZABBIX_WEBHOOK_TOKEN=         # shared secret for /zabbix/webhook/, must match the Zabbix
                               # Webhook media type's "token" parameter

# Live Streaming (streaming/ app) — see "Live Streaming — External Infrastructure" below
MEDIAMTX_WHIP_URL=            # public MediaMTX WHIP endpoint (browser publish), e.g. https://media.domain/
MEDIAMTX_WHEP_URL=            # public MediaMTX WHEP endpoint (browser playback), usually same as above
MEDIAMTX_AUTH_SECRET=         # shared secret, must match key= in mediamtx.yml's authHTTPAddress + the
                               # "mtx-internal" ffmpeg RTSP credential in runOnReady
WEBRTC_ICE_SERVERS=            # JSON RTCIceServer list (urls/username/credential) used by the browser
FASOP_PUBLIC_ORIGIN=          # Django's own public origin, e.g. https://fasop.domain — copied into
                               # mediamtx.yml's webrtcAllowOrigins by deploy/setup_streaming.sh
TURN_URL=                     # e.g. turn:203.0.113.10:3478 — copied into mediamtx.yml's webrtcICEServers2
TURN_USERNAME=                # coturn long-term-credential username (must match /etc/turnserver.conf)
TURN_PASSWORD=                # coturn long-term-credential password (must match /etc/turnserver.conf)
STREAMING_RECORDINGS_ROOT=     # must match recordPath's base dir in mediamtx.yml, readable by Django
STREAMING_RECORDING_RETENTION_DAYS=7
STREAMING_USE_X_ACCEL_REDIRECT=False   # True = serve recordings via nginx X-Accel-Redirect instead of
                                        # streaming through Django/gunicorn — see deploy/nginx-recordings-x-accel.conf.example
STREAMING_X_ACCEL_REDIRECT_PREFIX=/internal-recordings/
```

Changing `SECRET_KEY` in production invalidates all Hashids-encoded URLs and active sessions.

---

## Live Streaming — External Infrastructure

The `streaming` app doesn't add any new pip packages — WebRTC is handled entirely by the browser and by external, separately-installed infrastructure (not part of `requirements.txt`, not started by `runserver`/gunicorn):

| Component | Role | Install |
|---|---|---|
| **MediaMTX** | Media server — WHIP (publish)/WHEP (playback) over WebRTC, RTSP internally, records to fMP4 | Binary release from `github.com/bluenviron/mediamtx`, run as its own systemd service (`deploy/mediamtx.service` template, `deploy/mediamtx.yml` config template) |
| **coturn** | TURN/STUN relay — required for field technicians' phones behind mobile carrier CGNAT | `apt install coturn` (`deploy/turnserver.conf.example`) |
| **ffmpeg** | Server-side recording transcode: browsers always publish WebRTC video as VP8, but MediaMTX's fMP4 recorder doesn't implement VP8 — a local `ffmpeg` process (spawned by MediaMTX's `runOnReady` hook per live session) reads the raw feed over loopback RTSP and republishes it as H.264 to a separate `<key>-rec` path, which is what actually gets recorded | `apt install ffmpeg` — **hard dependency**, recording produces nothing at all without it (not just audio-only) |
| **Cloudflare Tunnel** (`cloudflared`) | How the FASOP production deployment exposes MediaMTX's WebRTC HTTP endpoint (`:8889`) to the public internet without opening inbound ports directly; forced to `--protocol http2` in the systemd unit because the default QUIC transport gets mangled by the office network | Already deployed for the main FASOP domain; a second public hostname is added for the media subdomain via the Cloudflare Zero Trust dashboard (Networks → Tunnels → Public Hostname), **not** by editing the local `config.yml` if the tunnel is dashboard-managed |
| nginx (alternative) | If a domain+cert already exists for FASOP and Cloudflare Tunnel isn't used, nginx can instead reverse-proxy HTTPS to MediaMTX on `localhost:8889` | See `deploy/nginx-mediamtx.conf.example` |
| nginx (optional, recordings) | Faster recording playback — nginx serves the recording file bytes directly (`X-Accel-Redirect`, including Range requests for seeking) instead of Django/gunicorn streaming them manually. Opt-in, off by default | Add a `location /internal-recordings/ { internal; alias <STREAMING_RECORDINGS_ROOT>/; }` snippet to the **existing** FASOP nginx server block, then set `STREAMING_USE_X_ACCEL_REDIRECT=True` — see `deploy/nginx-recordings-x-accel.conf.example` |

Setup script: `bash deploy/setup_streaming.sh` — idempotent, generates `deploy/mediamtx.generated.yml` (gitignored, contains secrets) from the `deploy/mediamtx.yml` template + `.env`, checks for `ffmpeg`, sets up the `purge_old_recordings` cron. **`mediamtx.generated.yml` is rewritten from scratch on every run** — never hand-edit it directly (origin/TURN values in particular have been lost this way before); all environment-specific values belong in `.env` (see table above) so re-running the script is always safe. Full walkthrough: `deploy/DEPLOY_CHECKLIST.md`.

---

## Inspeksi — Skema Kolom & Laporan Harian (`inspection/laporan.py`)

`inspection/laporan.py` adalah **satu-satunya** tempat yang mendefinisikan kolom
hasil inspeksi per jenis peralatan (`KOLOM_JENIS`). Tiga konsumennya memakai
skema yang sama, jadi tampilan layar, file Excel harian, dan rekap bulanan tidak
mungkin berbeda kolom:

| Konsumen | Kode |
|---|---|
| Halaman **Hasil Inspeksi Harian** (`/inspection/harian/`) — pilih tanggal, tab per jenis peralatan | `views.inspection_harian` |
| Export Excel harian (tombol di halaman itu **dan** cron jam 12.00) | `views.inspection_harian_export`, `management/commands/export_inspeksi_harian.py` |
| Rekap bulanan per ULTG | `views.inspection_export_ultg` |

Yang perlu diketahui saat menambah field inspeksi baru:

- **Tambahkan kolomnya di `KOLOM_JENIS`, bukan di header masing-masing view.**
  Sebelum ini header ditulis ulang per view; akibatnya sheet non-Catu-Daya
  memakai kolom rele (`kebersihan_panel`/`kondisi_relay`/`sumber_dc`) untuk
  semua jenis — kalau DFR/Server ADS diikutkan, seluruh barisnya jatuh ke blok
  `except` dan keluar sebagai strip.
- **`ok=` harus salah satu nilai `*_CHOICES` field itu.** Salah ketik membuat
  nilai normal ditandai alarm selamanya. Nilai `ok` UFLS memang beda dengan
  Master Trip (`on_aktif`/`terpasang` vs `on`/`normal`) meski labelnya mirip.
- **`alarm=True` harus konsisten dengan `is_alarm_inspection()`** di file yang
  sama — itu yang dipakai dashboard dan notifikasi WhatsApp, jadi kalau
  keduanya berbeda, angka "alarm" di laporan tidak cocok dengan yang di
  dashboard.
- Perangkat yang **belum** diinspeksi ikut dikembalikan `baris_harian()` dengan
  status `belum` — laporan harian gunanya menunjukkan cakupan, bukan cuma yang
  terisi. Perangkat berstatus Tidak Operasi tidak pernah ikut
  (`perangkat_operasi()`).
- Hasil telekomunikasi punya **dua jalur** (`Inspection` jenis `telecom` dari
  form inservice, dan `PengujianTelecomItem` dari form batch dispatcher).
  `baris_harian()` menggabungkan keduanya; kalau hanya satu yang dibaca,
  Radio/VoIP tampil "belum diinspeksi" padahal dispatcher sudah mengujinya.

Arsip harian ke share `\\192.168.77.5\fasop\inspeksi harian` memakai path yang
sudah di-mount (Django menulis file biasa, tidak berbicara SMB sendiri) —
pemasangan mount, `.env`, dan cron-nya di `deploy/EXPORT_INSPEKSI_HARIAN.md`
(`bash deploy/setup_inspeksi_export_cron.sh`).

---

## Kinerja SCADATEL — OFDB (`up2bmakassar/`)

Sumber data: **OFDB** = `dbup2bmakasar` di MSSQL 192.168.19.1, database offline SCADA milik aplikasi up2bmakassar. FASOP membacanya **read-only** lewat user `fasop_readonly` (`up2bmakassar/ofdb.py`, env `OFDB_*`) dan tidak pernah menulis ke sana. Hasil perhitungan disimpan di PostgreSQL (`KinerjaAnalogHarian`, `KinerjaDigitalHarian`, `RemoteControl`); SOE log tidak disimpan sama sekali (query on-demand).

Dua hal yang harus sama dengan app up2bmakassar kalau angkanya mau cocok:

- **Jenis titik ditentukan INDUK point type, bukan `point_type`.** `scd_c_point.id_pointtype` → `scd_pointtype.id_induk_pointtype`, namanya `TELEMETERING` (analog) / `TELESIGNAL`, `RTU`, `MASTER`, `TELEKOMUNIKASI` (semuanya digital). Halaman Telesignal di up2bmakassar memfilter `id_induk_pointtype=21`, Telemetering `=15`. Menghitung dengan `point_type='D'` saja akan mencampur RTU/Master/Telkom ke dalam angka Telesignal. Satu tabel digital menampung semua jenis, dibedakan lewat kolom `jenis` — sama seperti `scd_kin_digital_bulan` di app lama.
- **Availability = `SUM(uptime) / SUM(alltime) × 100`**, bukan rata-rata kolom `performance` harian — konsisten dengan serializer rekap up2bmakassar (bobot per hari jadi benar).

Perhitungan harian (`up2bmakassar/sync.py`) memakai **3 query per hari per jenis** (master titik, satu `GROUP BY` uptime untuk semua titik, satu lookup status terakhir untuk titik tanpa transisi). Script asli up2bmakassar memakai 4 query **per titik** — puluhan ribu round-trip ke 192.168.19.1 yang praktis tidak pernah selesai. Jangan kembali ke pola per-titik saat menambah jenis/metrik baru.

**Jebakan di sisi OFDB — flag `kinerja` bisa menempel di titik mati.** `point_number` bukan identitas abadi: kalau database Spectrum di-rebuild, titik yang sama muncul dengan nomor baru. Job sinkronisasi up2bmakassar (`syncoffline/apps/sync_offline/jobs/points.py`) menulis `kinerja = 0` baik saat INSERT maupun UPDATE, jadi titik baru selalu masuk tanpa flag dan flag `kinerja=1` tertinggal di baris lama yang sudah tidak punya data di `scd_*_rtl`/`scd_his_*`. Gejalanya: semua titik keluar 0% padahal tabel histori jelas terisi. Identitas logis titik adalah kombinasi `path1..path5` (B1/B2/B3/Element/Info), bukan `point_number` — `sync_kinerja_* --petakan-path` memakai itu untuk mencocokkan titik kinerja ke nomor yang masih hidup. Itu penambal; perbaikan sebenarnya adalah menandai ulang `kinerja=1` di master data up2bmakassar (dan memperbaiki `points.py` supaya tidak me-reset flag-nya).

Cron harian dipasang lewat `bash deploy/setup_kinerja_cron.sh [berdata|kinerja]` (idempotent): `sync_kinerja_analog` 01:10, `sync_kinerja_digital` 01:20, `sync_rc` 01:30 — semuanya `--days 3`. Argumen kedua `sering` (mis. `setup_kinerja_cron.sh berdata sering`) menjadwalkan `sync_rc` tiap 15 menit kalau RC perlu terlihat di hari yang sama; itu murah karena RC yang hasilnya sudah final (lewat 10 menit sejak perintah) tidak di-resolve ulang ke OFDB supaya satu malam yang gagal otomatis tersusul malam berikutnya. Dini hari karena availability dihitung per batas hari penuh (00:00–24:00), jadi angka sebuah hari baru final setelah tengah malam.

Kalau halaman kosong atau angkanya mencurigakan, jalankan `python manage.py cek_kinerja_ofdb` dulu — itu menunjukkan apakah masalahnya koneksi, nama induk point type, filter `SitePath1`, kecepatan query OFDB, atau memang cron sync-nya belum jalan. Index OFDB yang disarankan (dieksekusi DBA OFDB, bukan oleh FASOP): `deploy/ofdb_indexes.sql`.

---

## OPSIS — Prediksi Beban (spreadsheet, bukan ML)

Seri prediksi di chart "Beban Kit — Hari Ini" dan halaman `/opsis/prediksi-beban/`
sekarang berasal dari **Dashboard ROH Sulbagsel** (Rencana Operasi Harian), yang
diunggah sebagai file .xlsx ke Google Drive dan dikirim n8n
ke `POST /api/v1/prakiraan-beban/` → `opsis.PrakiraanBeban` (grid 30 menit, 48 titik
per hari, total sistem). Pola yang sama dengan HOP (`/api/v1/hop/`). Walkthrough
lengkap + bentuk spreadsheet: `docs/PRAKIRAAN_BEBAN_N8N.md`, dengan dua workflow
siap-impor di `docs/n8n_prakiraan_beban*.workflow.json`.

File di Drive itu **.xlsx hasil upload, bukan dokumen Google Sheets asli** — node
Google Sheets di n8n akan menolaknya (`must not be an Office file`), jadi yang
dipakai adalah Google Drive (Download) + Extract From File. Konsekuensinya sel
Tanggal/Jam datang sebagai angka serial Excel atau objek Date, bukan teks; node
Code di workflow itulah yang menormalkannya jadi `menit` sebelum dikirim ke FASOP.

Pemilihan sumber ada di **`opsis/prediksi.py`** — itu satu-satunya modul yang boleh
dipanggil views:

| Sumber (`OPSIS_FORECAST_SOURCE`) | Implementasi | Catatan |
|---|---|---|
| `sheet` (default) | `opsis/prakiraan.py` | ORM + datetime saja, tanpa pandas/numpy |
| `ml` | `opsis/forecast.py` | HistGradientBoostingRegressor, butuh cron `train_beban_forecast` |

Keduanya mengembalikan dict dengan kunci **identik** (`predict_beban_hari_ini`,
`predict_besok_puncak`, `evaluate_accuracy`) — kalau menambah field baru di salah
satu, tambahkan di keduanya, jangan biarkan UI bercabang per sumber. Modul ML tidak
di-import selama sumbernya `sheet`, jadi `scikit-learn`/`joblib` boleh absen di
runtime meski masih tercantum di `requirements.txt`.

Keterangan sumber ("Dashboard ROH Sulbagsel") ditampilkan di bawah chart beban dan
di halaman analitik, teksnya mengikuti `source` dari API (`sheet`/`no_sheet`/`model`/
`no_model`/`mssql`) — jangan hardcode nama sumber di satu tempat saja kalau nanti
`OPSIS_FORECAST_SOURCE` diubah.

Baris `PrakiraanBeban` hari lampau **tidak pernah dihapus** — histori itulah yang
dipakai `evaluate_accuracy()` untuk membandingkan prakiraan vs realisasi `SnapLive`.
Menimpa kurva hari yang sudah lewat dengan angka realisasi akan membuat akurasi
terlihat sempurna secara palsu.

---

## OPSIS — Peta Sumber Data (`/opsis/sumber-data/`)

OPSIS menarik angka dari **17 sumber**: 9 tabel MSSQL, 6 tabel snapshot
PostgreSQL yang diisi cron, dan 2 sumber luar lewat n8n. Halaman ini
menampilkan petanya lengkap dengan status kesegaran tiap sumber, dan itulah
tempat pertama yang dibuka saat sebuah angka mencurigakan.

Alasannya konkret: `SYS_FREQ_HIS` pernah berhenti diisi **42 jam tanpa
ketahuan**, karena kartu Hz di dashboard membaca `SYS_FREQ_RT` — tabel LAIN yang
kebetulan masih hidup. Tanpa peta, tidak ada satu layar pun yang bisa
menunjukkan bahwa dua angka "frekuensi" di aplikasi yang sama datang dari tabel
berbeda dengan nasib berbeda.

Petanya **deklaratif** di `opsis/sumber_data.py` (list `SUMBER`). Menambah
sumber baru = menambah satu entri, bukan menulis kode. Tiap entri menyebut fitur
pemakainya, tabel/model, hulu, siapa yang mengisi, dan catatan jebakannya.

Tiga hal yang menentukan halaman ini jujur:

- **`waktu_andal: False`** menandai kolom waktu yang ADA tapi tidak dipelihara —
  `KIT_REALTIME.DATE` dan `KIT_DMP.DATE`. Nilainya tetap ditampilkan sebagai
  keterangan, tapi statusnya `tak_andal`, **bukan** `mati`. Tanpa penanda ini
  halaman melaporkan dashboard mati padahal angkanya jelas hidup.
- **`lewati_periksa: True`** untuk sumber yang tidak punya satu tabel tunggal
  (`TRANS_*_RT`, `TitikEWS.sumber_tabel` yang dipetakan per titik).
- **`LAPIS_URUT` + sort di `periksa_semua()`.** `{% regroup %}` di template hanya
  menggabungkan item yang BERURUTAN; tanpa pengurutan, satu lapisan muncul dua
  kali begitu ada entri disisipkan di tempat yang salah.

Sebagian besar tabel realtime MSSQL (`SYS_FREQ_RT`, `ALL_TRANS_DATA`,
`IND_LOAD`, `TRANS_*_RT`) **tidak punya kolom waktu sama sekali** — nilainya
ditimpa di tempat. Kesegarannya hanya bisa dinilai lewat tabel snapshot
PostgreSQL yang menyalinnya. Ini alasan struktural kenapa lapis PostgreSQL tidak
bisa dihapus begitu saja meski terasa duplikatif.

---

## OPSIS — Armada KIT: Dashboard vs Respons Pembangkit

Dashboard dan Respons Pembangkit membaca **tabel historian yang berbeda**, dan
isi armadanya tidak selalu sama:

| | Dashboard | Respons Pembangkit |
|---|---|---|
| Sumber MSSQL | `KIT_REALTIME` | `HIS_MEAS_KIT` |
| Penentu daftar | `opsis.Pembangkit` (`kit_source()` + `unit_whitelist()`) | `RESPON_PLANTS` (`opsis/respon_registry.py`) |

Perhitungan MW-nya **sama** di kedua jalur (`abs(P)` per unit lalu dijumlahkan),
jadi kalau totalnya berbeda, penyebabnya hampir pasti armada — bukan rumus.
Pernah terukur selisih 32 MW: `BMPP25` (BMPP WOLO, ~58 MW) ada di `KIT_REALTIME`
tapi **sama sekali tidak direkam di `HIS_MEAS_KIT`**, sementara `PLTMH` (~27 MW)
sebaliknya — ada di historian tapi belum punya baris `Pembangkit` sehingga tidak
ikut terhitung di Dashboard.

Jalankan `python manage.py cek_armada_kit` sebelum menyimpulkan apa pun tentang
selisih MW. Command itu membandingkan keempat tempat sekaligus (KIT_REALTIME,
HIS_MEAS_KIT, `Pembangkit`, `RESPON_PLANTS`) dan menyebut mana yang bisa
diperbaiki dari FASOP dan mana yang tidak:

- **KIT ada di `KIT_REALTIME` tapi tidak di `HIS_MEAS_KIT`** — tidak bisa
  diperbaiki dari FASOP. Menambahkannya ke `RESPON_PLANTS` percuma, datanya
  memang tidak ada; yang perlu diminta adalah pengelola historian merekamnya.
- **KIT ada di historian tapi tidak punya `Pembangkit`** — cukup tambah barisnya
  di Admin → Opsis → Pembangkit, tanpa ubah kode.
- **KIT di `RESPON_PLANTS` yang tidak punya data** — kode lama, bersihkan dari
  registry supaya tidak menyesatkan.

Catatan lain: kolom `DATE` di `KIT_REALTIME` **tidak dipelihara** — banyak baris
bertanggal 2022–2025 padahal nilainya terbarui terus. Jangan pakai kolom itu
untuk menilai kesegaran data.

---

## OPSIS — Ekspor Beban per Pembangkit (`/opsis/export/beban-pembangkit/`)

Unduhan Excel berisi riwayat beban **semua pembangkit aktif**, satu sheet per
pembangkit (nama sheet = nama pembangkit), plus sheet **Ringkasan Sistem** di
depan (total MW + Hz per menit) dan sheet **Keterangan** di belakang. Tombolnya
di dashboard, di atas grid pembangkit, dengan dua kotak tanggal.

Gunanya bukan sekadar ekspor: ini **cadangan manual untuk analisis Respons
Pembangkit**. Sumbernya PostgreSQL (`SnapLive`), bukan MSSQL, jadi tetap bisa
diunduh saat historian tak terjangkau atau saat Respons Kit sedang tidak jalan —
tiap sheet memuat MW, MVAR, dan Hz sistem per menit sehingga respons tiap
pembangkit terhadap ayunan frekuensi masih bisa ditelusuri manual.

Dua hal yang menentukan halaman ini tetap cepat, jangan dibalik tanpa mengukur:

- **Batas rentang memakai datetime, bukan lookup `__date`.** `waktu__date__gte`
  membungkus kolom dalam fungsi cast sehingga indeks `(pembangkit, -waktu)`
  tidak terpakai dan tiap sheet memicu sequential scan atas jutaan baris
  `SnapLive`. Mengukurnya: ekspor 1 hari turun dari 18,9 detik jadi 5,6 detik
  setelah diganti `waktu__gte=awal, waktu__lt=akhir`.
- **`openpyxl.Workbook(write_only=True)`.** Mode biasa merakit objek `Cell`
  untuk tiap sel; satu hari × 23 pembangkit sudah ~200 ribu sel. Konsekuensinya
  sel tidak bisa disentuh lagi setelah `append`, jadi seluruh gaya dipasang saat
  baris dibuat (lihat `_buat_sheet`).

Rentang dibatasi `EXPORT_KIT_MAKS_HARI` (7 hari, ~30 detik) supaya satu worker
gunicorn tidak tertahan sampai timeout. Nama sheet dibersihkan dan diunikkan
sendiri oleh `_nama_sheet()` — Excel melarang `[]:*?/\` dan memotong di 31
karakter, jadi dua pembangkit berawalan sama bisa bertabrakan dan openpyxl akan
melempar error di tengah perakitan kalau tidak ditangani lebih dulu.

---

## OPSIS — Riwayat Frekuensi (tiga sumber)

Riwayat frekuensi sistem dibaca lewat **`opsis/freq_history.py`** — satu-satunya
modul yang boleh dipanggil views/command. Jangan kembali memanggil
`mssql.get_freq_range()` langsung: kalau begitu salah satu jalur (halaman atau
cron `deteksi_respon`) akan kehilangan tambalannya.

Ada **tiga** sumber, digabung per detik menurut prioritas. Detik yang sudah
terisi sumber di atasnya tidak pernah ditimpa sumber di bawahnya:

| # | Sumber | Asal | Menolong saat |
|---|---|---|---|
| 1 | `SYS_FREQ_HIS` (MSSQL) | historian SCADA, 1 baris/detik | **acuan** — dipakai di detik mana pun ia punya data |
| 2 | `opsis.SnapFreq` (PostgreSQL) | cermin no.1, diisi cron `collect_freq` | **MSSQL tak terjangkau** (koneksi putus / circuit breaker terbuka) |
| 3 | `opsis.SnapFreqRT` (PostgreSQL) | rekaman FASOP sendiri dari `SYS_FREQ_RT` lewat cron `collect_freq_rt` | **job penulis `SYS_FREQ_HIS` berhenti diisi** |

Dua mode kegagalan terakhir itu **berbeda dan butuh penambal berbeda**. No.2
tidak bisa menggantikan no.3: ia cermin dari no.1, jadi saat sumbernya berhenti
diisi, cerminnya ikut kosong di rentang yang sama. Jangan hapus salah satunya
dengan alasan "sudah ada yang lain".

Kenapa begitu: job penulis `SYS_FREQ_HIS` di sisi SCADA pernah berhenti
berhari-hari (24 Agustus 2026 15:17, didahului pemadaman parsial sejak 19
Agustus) dan **seluruh Respons Pembangkit ikut mati** — padahal `SYS_FREQ_RT` di
server yang sama tetap hidup, dan kartu Hz di dashboard (yang membaca RT) tetap
normal sehingga masalahnya tidak kelihatan selama ±42 jam. Dengan penggabungan
ini, historian tetap jadi acuan begitu pulih, tanpa perlu mengganti setelan.

Yang perlu diketahui saat mengubahnya:

- **Historian selalu menang** di detik yang sama. `SnapFreqRT` hanya mengisi
  detik kosong, jadi angka resmi tidak pernah tertimpa rekaman sendiri.
- **Zona waktu harus disamakan.** MSSQL mengembalikan datetime *naive* (waktu
  lokal server historian), PostgreSQL menyimpan *aware* (UTC, karena
  `USE_TZ=True`). Tanpa `_ke_naive_lokal()`, kedua deret meleset 8 jam saat
  digabung — dan hasilnya tetap "terlihat wajar", jadi tidak akan ketahuan
  kecuali dicek.
- **Resolusi menentukan gunanya.** Analisis respons memakai jendela −60/+180
  detik; pada 1 sampel/menit itu cuma ~4 titik dan ayunan 10–20 detik tak
  terlihat. Cron harus `collect_freq_rt --loop --interval 1 --durasi 55`
  (1 sampel/detik, menyamai `SYS_FREQ_HIS`), bukan `collect_freq_rt` polos.
  Pasang lewat `bash deploy/setup_freq_rt_cron.sh` (idempotent).
- `ambil_range_detail()` mengembalikan `(deret, info)` dengan hitungan berapa
  detik benar-benar DIPAKAI dari masing-masing sumber (`historian`/`snapfreq`/
  `postgres`) — bukan berapa yang tersedia, supaya angkanya terbaca sebagai
  "berapa yang ditambal". `keterangan(info)` memberi teksnya untuk ditampilkan;
  pakai itu daripada mengarang label sumber di template.
- Urutan prioritas ditentukan **urutan tuple** di `ambil_range_detail()`. Menukar
  barisnya menukar siapa yang menang — jangan diubah tanpa sengaja.
- Rekaman ini **tidak bisa mengisi masa lalu**. Lubang sebelum cron dipasang
  hanya bisa dipulihkan dari arsip historian — perbaikan di sisi SCADA tetap
  perlu dikejar.

---

## OPSIS — Mode Pemeliharaan (`opsis.ModePemeliharaan`)

Sakelar tunggal di site admin (**Opsis → Mode Pemeliharaan OPSIS**, satu baris
pk=1, tombol Tambah/Hapus dimatikan) yang menutup **seluruh** `/opsis/*` dan
menggantinya dengan `opsis/pemeliharaan.html` (HTTP 503 + `Retry-After`).
Dipakai mis. selama koneksi ke historian MSSQL belum tersedia, supaya halaman
OPSIS tidak menampilkan angka kosong sambil menembak MSSQL terus-menerus.

Penegakannya di `devices.middleware.OpsisMaintenanceMiddleware`, **bukan** di
tiap view — jadi rute OPSIS baru otomatis ikut tertutup tanpa perlu diingat.
Yang perlu diketahui saat mengubahnya:

- Permintaan ke `/opsis/api/*` (dan XHR lain) dijawab **JSON** 503, bukan HTML,
  supaya poller tidak menelan HTML sebagai JSON.
- Superuser tetap bisa masuk selama `boleh_superuser` dicentang; request-nya
  ditandai `request.opsis_pemeliharaan = True` dan `opsis_base.html` menampilkan
  pita penanda. Hilangkan centangnya untuk menutup OPSIS tanpa kecuali.
- `ModePemeliharaan.status()` men-cache barisnya `TTL_CACHE` detik per proses
  (dibaca tiap request `/opsis/*`), dan `save()` menyegarkan cache di worker yang
  menyimpan. Jadi perubahan dari admin berlaku instan di satu worker dan paling
  lambat beberapa detik di worker lain — jangan ganti jadi query per request.
- Cron pengumpul data (`collect_live`, `collect_freq`, dsb.) tidak lewat
  middleware sama sekali, jadi pengumpulan data tetap jalan selama pemeliharaan.

---

## OPSIS — Peta Pembangkit (`/opsis/peta/`)

Peta sebaran pembangkit se-Sulawesi: ikon per jenis (PLTA/PLTU/PLTD/…) berisi
daya aktifnya, plus tabel DMN / P / Q semua pembangkit di kartu sebelah kanan.
Halaman ini **tidak punya endpoint API sendiri** — ia memoll `/opsis/api/live/`
yang sama dengan dashboard tiap 5 detik, supaya angka di peta, tabel, dan kartu
dashboard tidak pernah berbeda. Kalau perlu field baru di peta, tambahkan di
`api_live()` sekali, jangan bikin endpoint kedua.

Posisi pin diselesaikan `Pembangkit.posisi_peta()` dengan urutan: `peta_x`/`peta_y`
(persen viewBox — diisi lewat mode **Atur Peta** di halaman itu sendiri, atau
manual dari site admin) → `hop_map.posisi_pembangkit(nama)` (tabel bawaan,
pencocokan nama mengabaikan spasi/tanda baca) → tidak dipetakan (pembangkit tetap
muncul di tabel + disebut di catatan bawah peta). Menambah entri permanen
dilakukan di `_EXTRA_LATLON` (`opsis/hop_map.py`) sebagai lat/long, diproyeksikan
`proyeksi()` dengan konstanta yang sama seperti pin dashboard HOP — jangan
mengarang persen langsung supaya peta HOP dan Peta Pembangkit tetap sebidang.

**Mode Atur Peta** (tombol di kanan atas, hanya superuser/role Opsis — aturan
`_bisa_atur_peta()`, sama dengan penanda ketidaksesuaian data): ikon diseret
langsung di peta, pembangkit yang belum punya ikon diseret dari daftar "Tidak
tampil di peta" ke peta, "Posisi bawaan" mengosongkan `peta_x`/`peta_y` lagi, dan
"Sembunyikan" mematikan `tampil_di_peta`. Semua perubahan baru masuk database saat
Simpan ditekan (`POST /opsis/peta/simpan/`, body JSON
`{posisi:[{pk,x,y}], hapus:[pk], sembunyi:[pk]}`), lalu halaman dimuat ulang.

**Ikon kelompok (`opsis.KelompokPeta`).** Satu ikon bisa mewakili beberapa
pembangkit sekaligus (mis. rumpun Tello) supaya peta hanya menampilkan titik
besar. Dibuat lewat **Atur Peta → Ikon kelompok baru** (atau site admin):
namanya tampil sebagai keterangan di bawah ikon, lencana kecil menunjukkan jumlah
anggota, dan tooltip memuat daftar anggota beserta dayanya. Dayanya **tidak
disimpan** — dijumlahkan di browser dari `NILAI` (isi `/opsis/api/live/`) yang
sama dengan ikon biasa, jadi angka peta dan tabel tidak mungkin berbeda.
Pembangkit yang jadi anggota kelompok yang tampil **tidak** digambar sebagai ikon
sendiri dan sengaja tidak masuk daftar "Tidak tampil di peta" — kalau masuk, ia
bisa diseret jadi ikon kedua dan dayanya terhitung dua kali di peta. Semuanya
tetap ada di tabel daya.

**Tampil/sembunyi terpisah dari koordinat.** Mengosongkan `peta_x`/`peta_y` TIDAK
menghilangkan ikon — pembangkit yang namanya terdaftar di `hop_map.py` muncul lagi
di posisi bawaannya. Yang menentukan muncul-tidaknya ikon adalah
`Pembangkit.tampil_di_peta` (juga bisa dicentang massal dari daftar admin, mis.
untuk hanya menampilkan pembangkit berbeban besar). Pembangkit yang disembunyikan
tetap masuk tabel daya di sebelah peta.

Berkas SVG peta dan ikon yang bisa diedit ada di `docs/peta/` (lihat README di
sana untuk cara mengembalikan hasil editnya ke kode).

Pembangkit yang berdekatan (rumpun Tello, gugusan Manado) digeser `_sebar_pin()`
di `opsis/views.py` supaya ikon + label MW-nya tidak bertumpuk; ambangnya
`PIN_MIN_DX`/`PIN_MIN_DY` — sesuaikan keduanya bila ukuran ikon/label di template
diubah, kalau tidak label akan mulai saling menimpa lagi. Pin dengan posisi manual
**tidak pernah ikut digeser** — kalau aturan itu dilonggarkan, hasil seret-lepas
akan pindah sendiri begitu halaman dimuat ulang.

Warna per jenis pembangkit hidup di `opsis.models.JENIS_WARNA` dan dikirim ke
template lewat `json_script`. Jangan menyalin dict warna itu ke dalam `<script>`
template baru.

---

## OPSIS — EWS Defense Scheme (`/opsis/ews/`)

Halaman peringatan dini yang menunjukkan **jarak nilai ukur realtime terhadap
ambang setting rele defense scheme** (UVLS, OVTS, OVCS, UVRS, OFGS, UFLS, OLS,
OGS, ADS, UPLS, ISLAND) — supaya skema yang mendekati ambang kerjanya terlihat
sebelum skema itu benar-benar bekerja.

Seluruh isinya **data, bukan kode**: kolom parameter (`opsis.KolomEWS`) dan
titiknya (`opsis.TitikEWS`) didaftarkan lewat site admin — termasuk tabel dan
kolom MSSQL tempat nilai ukurnya dibaca. Menambah skema baru **tidak perlu
migrasi maupun redeploy**, sama seperti menambah Pembangkit. Isi awal 93 titik
dari berkas *Defense Scheme UP2B Makassar 2026.xlsx* dipasang dengan
`python manage.py seed_ews` (idempotent).

**Pemetaan ke MSSQL: tabel + kolom nilai + kolom kunci + nilai kunci.** Bentuknya
sengaja sama dengan `opsis.Trafo.sumber_*` — mis. `dbo.SYS_FREQ_RT` / `VALUE` /
`ANALOG` / `FREQ_MKS`. `faktor_skala` mengubah satuan (0.001 bila historian
menyimpan Volt sementara halaman menampilkan kV). Kolom kunci yang dikosongkan
berarti tabelnya hanya satu baris (`SELECT TOP 1`). `sumber_tabel` kosong =
titik tampil "belum termonitor", bukan error.

Yang perlu diketahui saat mengubahnya:

- **`get_nilai_ews()` mengelompokkan titik per `(tabel, kolom_kunci, kolom_nilai)`
  dan menembak SATU query `IN (...)` per kelompok.** Jangan diubah jadi satu
  query per titik: 93 titik pada 2 tabel harus tetap 2 query tiap poll, bukan 93.
  Pola per-titik inilah yang dulu membuat sinkronisasi OFDB praktis tidak selesai
  (lihat "Kinerja SCADATEL"). Kunci di-chunk 200 per query (batas 2100 parameter
  SQL Server).
- **Nama tabel/kolom datang dari input admin, jadi tidak bisa jadi bind parameter.**
  Semuanya divalidasi `_TABLE_RE`/`_COLUMN_RE` dulu dan kelompok yang tidak lolos
  dilewati dengan `logger.error` tanpa pernah menyentuh SQL; **nilai** kunci tetap
  lewat `?`. Aturan ini wajib diikuti kalau menambah field sumber baru.
- **Margin dan status dihitung di `TitikEWS.margin()`/`.status()` (Python), bukan
  di JavaScript.** Template hanya menggambar. Kalau nanti ditambah blast WhatsApp,
  alert dan tampilan otomatis memakai aturan yang sama — jangan menyalin ulang
  perhitungannya ke `<script>`.
- Margin dinormalkan agar bisa diurutkan lintas besaran: pecahan terhadap nominal
  (tegangan), Hz absolut (frekuensi), pecahan terhadap setting (arus/daya).
  Ambang waspada bawaan ada di `AMBANG_WASPADA_DEFAULT`, bisa ditimpa per titik.
- `/opsis/api/ews/` dibungkus `_hz_cached('ews', ...)` TTL 2 detik sementara
  browser memoll tiap 5 detik — satu query per worker walau banyak tab terbuka.
  Ini penjaga yang sama dengan endpoint Hz; jangan dilepas.
- Warna tag skema hidup di `opsis.models.SKEMA_WARNA` dan dikirim ke template
  lewat `json_script`. Jangan menyalin dict itu ke `<script>` template baru.

**Ambang setting disunting langsung dari kartu, pemetaan MSSQL tidak.** Tombol
pensil di kartu (`/opsis/ews/simpan/`) membuka isian setting/nominal/arah/ambang
waspada/time delay untuk **teknisi (`role='technician'`) dan superuser** —
setting rele berubah di lapangan tanpa harus menunggu akses site admin. Field
`sumber_*` sengaja **tidak** ada di endpoint itu: salah ketik nama tabel tidak
boleh bisa terjadi dari layar monitoring, jadi mengarahkan titik ke historian
tetap hanya lewat site admin. Endpoint menerima koma desimal (`133,5`) karena
begitulah operator mengetik, dan setiap perubahan dicatat ke `auditlog` lengkap
dengan nilai lama → baru. Saat sebuah kartu sedang disunting, kolomnya tidak
digambar ulang oleh polling — kalau aturan itu dilepas, isian dan fokus kursor
akan terhapus tiap 5 detik di tengah pengetikan.

Belum tahu nama kolom sebuah tabel historian? `python manage.py probe_tabel_ews
dbo.KIT_REALTIME` menampilkan daftar kolom + baris contoh. Dari admin, aksi
**"Lihat kolom tabel sumber"** dan **"Uji baca nilai dari MSSQL"** (Opsis → Titik
EWS) menjawab "kenapa kartu saya kosong" tanpa membuka log server.

---

## Early Warning WhatsApp (OpenWA)

One self-hosted OpenWA gateway serves **three** alert sources. All of them go
through `device_mon.notifications.kirim_wa()` — the only place that speaks HTTP
to OpenWA. If the gateway is ever replaced, adjust `_build_url` /
`_build_headers` / `_build_payload` there; don't add a second client per app.

| Source | Trigger | Who gets sent | Destination |
|---|---|---|---|
| RTU (`alert_rtu`) | `collect_rtu` on UP/DOWN transition | RTU with `wa_alert=True` (default **True** — legacy behaviour) | `WA_CHAT_IDS` |
| `inspection` | Operator inspection alarm | always | `WA_CHAT_IDS_INSPECTION` |
| Zabbix (`alert_zabbix`) | `sync_zabbix` (pull) **and** the webhook (push) | host with `wa_alert=True` (default **False**) and severity ≥ `wa_min_severity` | host's `wa_chat_ids` → `WA_CHAT_IDS_ZABBIX` → `WA_CHAT_IDS` |

The differing defaults are deliberate: the RTU list is curated by hand, whereas
`ZabbixHost` rows are created **automatically** by `sync_zabbix` whenever a new
host appears in Zabbix. If the default were on, adding one host in Zabbix would
immediately flood the WhatsApp group with nobody having decided that. So new
hosts stay silent until ticked in Admin (`/secure-panel/` → Device Mon → Host
Zabbix), per host or via the bulk action "Aktifkan blast WhatsApp".

Rules that are easy to miss when adding a new alert:

- **There are two Zabbix transition points** (`sync_zabbix` and
  `views.zbx_webhook_receiver`), and both call the same `notif_zabbix_transisi()`.
  Add new notification channels inside that function, not in the two callers —
  otherwise the alert lives on the pull path and stays silent on the push path
  (or vice versa).
- **A "recovered" message is only sent if its PROBLEM message actually went out**
  (`_zbx_problem_terkirim()`). Without that the group receives "back to OK" for
  an incident they never heard about — which happens every time the problem was
  below the severity threshold or the gateway was down.
- **Skips are logged too.** `ZabbixAlertLog` / `RTUAlertLog` get a row even for
  deliberately skipped alerts, with the reason in `keterangan`. That is what
  answers "why didn't the notification arrive?" from Admin without reading
  server logs.
- `kirim_wa()` **never raises** — cron and webhook must keep working even when
  the WA gateway is dead. Preserve that property in any new helper.

Test the configuration without waiting for a real incident:

```bash
python manage.py test_wa --target rtu         # WA_CHAT_IDS
python manage.py test_wa --target inspection  # WA_CHAT_IDS_INSPECTION
python manage.py test_wa --target zabbix      # WA_CHAT_IDS_ZABBIX
```

Hosts using their own `wa_chat_ids` are not covered by that command — test them
with the **"Kirim pesan uji WA ke tujuan host terpilih"** action in
Admin > Host Zabbix.

The OpenWA gateway itself (Docker, same server) lives outside this repo:
`https://github.com/rmyndharis/OpenWA`. Its compose customisations belong in
`docker-compose.override.yml` in the OpenWA directory — never edit the tracked
`docker-compose.yml`, or `git checkout` during an upgrade will refuse to switch.

---

## OPSIS — Adding a New Power Plant

New plants are added via Django Admin (`/secure-panel/` → Opsis → Pembangkits), **not** through migrations. The `kode_kit` field must match exactly the `KIT` column value in the MSSQL `KIT_REALTIME` table. No redeploy needed.

---

## Production Deployment Checklist

```bash
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput   # only if static/ changed
sudo systemctl restart gunicorn
sudo systemctl reload nginx
```

Rollback: `git revert <commit>` then redeploy. Never edit files directly on the server.

If OPSIS worker isolation is set up (`deploy/OPSIS_WORKER_ISOLATION.md` — a
second gunicorn pool dedicated to `/opsis/*` so an MSSQL outage can't
exhaust workers for the rest of FASOP), also `sudo systemctl restart
fasop-opsis` on code deploys, same as the main `gunicorn`/`fasop` service.
