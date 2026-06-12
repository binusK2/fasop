# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FASOP** is a production Django 6.0 web application for PT. PLN (Persero) UIP3B Sulawesi. It manages telecommunications and SCADA equipment assets, preventive/corrective maintenance workflows, fault tickets, and real-time power system monitoring (OPSIS).

Tech stack: Django 6.0 + Python 3.12, PostgreSQL (primary), MSSQL via pyodbc (SCADA historian), Bootstrap 5, Chart.js 4 — no Node.js/npm build step.

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

Each of the 20+ Django apps follows a standard layout (`models.py`, `views.py`, `forms.py`, `urls.py`, `templates/<app>/`). Key apps:

| App | Responsibility |
|---|---|
| `devices/` | Core asset inventory (Device, FiberOptic, SiteLocation), dashboard, wiring diagram editor |
| `maintenance/` | Preventive/corrective maintenance, Berita Acara, digital signature workflow, PDF export |
| `gangguan/` | Fault ticket CRUD, status workflow, public status page |
| `opsis/` | Real-time power monitoring dashboard, MSSQL historian, data collection cron commands |
| `health_index/` | Equipment health scoring (0–100) |
| `inspection/` | Inservice inspection for Operator role |
| `gudang/` | Warehouse / spare parts inventory |
| `device_mon/` | RTU status monitoring |
| `scada_av/` | SCADA/RTU availability and RCD success rate |
| `api/` | REST API for n8n / Google Sheets integrations |
| `auditlog/` | Superuser audit logging |
| `fasop/` | Root settings, URL routing, Hashids helper, URL converters |

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
- **MSSQL** — read-only SCADA historian (`opsis/mssql.py`). If unreachable, the OPSIS dashboard falls back to PostgreSQL automatically. Never write to MSSQL.

MSSQL connection is established per-request in `opsis/mssql.py` with a 30-second timeout and a TCP reachability pre-check.

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
Modules: `opsis`, `devices`, `maintenance`, `gangguan`, `gudang`, `inspection`, etc.

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

# MSSQL SCADA historian (optional — OPSIS falls back to PostgreSQL if absent)
MSSQL_HOST=192.168.x.x,1433
MSSQL_DB=
MSSQL_USER=
MSSQL_PASS=
MSSQL_TABLE=dbo.HIS_MEAS_KIT
MSSQL_RT_TABLE=dbo.KIT_REALTIME
MSSQL_FREQ_TABLE=dbo.SYS_FREQ_HIS
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

API_KEY=              # For /api/v1/ integrations
```

Changing `SECRET_KEY` in production invalidates all Hashids-encoded URLs and active sessions.

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
