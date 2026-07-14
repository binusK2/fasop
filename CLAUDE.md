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
| `opsis/` | Real-time power monitoring dashboard, MSSQL historian, data collection cron commands |
| `health_index/` | Equipment health scoring (0–100), computed (not stored) from 9 weighted factors |
| `inspection/` | Inservice inspection for Operator role |
| `gudang/` | Warehouse / spare parts inventory; stock level is computed from `MutasiSparepart`, not a stored field |
| `device_mon/` | RTU UP/DOWN status monitoring (`collect_rtu` cron command) |
| `scada_av/` | SCADA/RTU availability and RCD success rate; wraps the `spectrum7_av/` calculation library |
| `notifikasi/` | In-app notification center (per-user + broadcast); other apps push notifications via `notif_ke_user()` / `notif_ke_am()` helpers |
| `jadwal/` | Monthly preventive-maintenance visit scheduling per location, with HI/age/device-count priority ranking |
| `common_enemy/` | Cross-cutting multi-site issue tickets (SCADA/telkom/prosis), auto-numbered `CE-YYYYMM-XXXX` |
| `dokumentasi/` | Relay setting & wiring-diagram document repository with uploader→checker approval workflow |
| `auditlog/` | Custom (not django-auditlog) superuser audit log; entries are created by explicit `log_action()` calls in views, not signals |
| `streaming/` | Field maintenance live streaming (WebRTC WHIP/WHEP via MediaMTX, `deploy/mediamtx.yml`); Teknisi broadcasts, Teknisi/AM view, only AM can join as Pengawas for 2-way talkback; teknisi's video is recorded (server-side ffmpeg transcode, see below) and pengawas's talkback audio is recorded as a **separate** clip (`LiveSession.talkback_recording_path`) rather than mixed into one file; recordings kept 7 days (`purge_old_recordings` cron) |
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
| `collect_rtu` | device_mon | Cron, every minute — RTU UP/DOWN from MSSQL `RTU_ALL_STATE` → `RTU`/`RTULog`; supports `--dry-run` |
| `generate_rename_plan` | devices | One-off — builds a device-rename plan for review before applying |
| `apply_rename_plan` | devices | One-off — applies a previously generated rename plan |
| `audit_device_names` | devices | One-off — reports naming inconsistencies across `Device` |
| `fix_notif_urls` | notifikasi | One-off — repairs malformed notification links |
| `purge_old_recordings` | streaming | Cron, daily — deletes `LiveSession` recording files past `STREAMING_RECORDING_RETENTION_DAYS` (default 7 days since `ended_at`); supports `--dry-run` |

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
