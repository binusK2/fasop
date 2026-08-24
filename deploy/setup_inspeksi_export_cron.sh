#!/usr/bin/env bash
#
# setup_inspeksi_export_cron.sh — pasang cron jam 12.00 untuk arsip Excel
# hasil inspeksi harian (app inspection).
#
# Idempotent: kalau baris cronnya sudah ada, dilewati (tidak dobel).
#
#   bash deploy/setup_inspeksi_export_cron.sh              # jam 12.00 (default)
#   bash deploy/setup_inspeksi_export_cron.sh "0 12,17 * * *"   # jadwal sendiri
#
# Yang dipasang:
#   12:00  export_inspeksi_harian --days 2
#
# --days 2 artinya hari ini + kemarin ikut ditulis ulang: kalau satu hari
# cronnya gagal (share NAS sempat lepas), hari berikutnya otomatis menyusul
# tanpa perlu backfill manual. File hari yang sama ditimpa, bukan ditambah.
#
# Tujuan file diambil dari INSPEKSI_EXPORT_DIR di .env. Share Windows harus
# sudah di-mount lebih dulu — lihat deploy/EXPORT_INSPEKSI_HARIAN.md.

set -euo pipefail

JADWAL="${1:-0 12 * * *}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo "Project : $PROJECT_ROOT"
echo "Python  : $PYTHON_BIN"
echo "Jadwal  : $JADWAL"
echo

TUJUAN="$(grep -E '^INSPEKSI_EXPORT_DIR=' "$PROJECT_ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
if [[ -z "$TUJUAN" ]]; then
    echo "PERINGATAN: INSPEKSI_EXPORT_DIR belum ada di .env — cron akan gagal"
    echo "            sampai diisi, mis: INSPEKSI_EXPORT_DIR=\"/mnt/fasop/inspeksi harian\""
elif [[ ! -d "$TUJUAN" ]]; then
    echo "PERINGATAN: folder tujuan belum ada / belum di-mount: $TUJUAN"
    echo "            lihat deploy/EXPORT_INSPEKSI_HARIAN.md"
else
    echo "Tujuan  : $TUJUAN (ada)"
fi
echo

NAMA="export_inspeksi_harian"
BARIS="$JADWAL cd $PROJECT_ROOT && $PYTHON_BIN manage.py $NAMA --days 2 >> $LOG_DIR/$NAMA.log 2>&1"

if crontab -l 2>/dev/null | grep -qF "manage.py $NAMA"; then
    echo "  [skip] $NAMA — cron sudah terpasang"
else
    (crontab -l 2>/dev/null || true; echo "$BARIS") | crontab -
    echo "  [ok]   $NAMA — $JADWAL"
fi

echo
echo "Cron terpasang:"
crontab -l | grep -F "manage.py $NAMA" || true
echo
echo "Uji sekarang tanpa menulis file:"
echo "  cd $PROJECT_ROOT && $PYTHON_BIN manage.py $NAMA --dry-run"
