#!/usr/bin/env bash
#
# setup_kinerja_cron.sh — pasang cron harian untuk Kinerja SCADATEL (app up2bmakassar).
#
# Idempotent: kalau baris cronnya sudah ada, dilewati (tidak dobel). Aman
# dijalankan ulang kapan saja.
#
#   bash deploy/setup_kinerja_cron.sh              # sumber titik: berdata (default)
#   bash deploy/setup_kinerja_cron.sh kinerja      # sumber titik: flag kinerja=1 di OFDB
#
# Yang dipasang (waktu server, dijeda supaya tidak menumpuk di OFDB):
#   01:10  sync_kinerja_analog   -- Telemetering
#   01:20  sync_kinerja_digital  -- Telesignal
#   01:30  sync_rc               -- log Remote Control
#
# Semuanya menghitung H-1 ke belakang beberapa hari (--days 3), jadi kalau satu
# malam cronnya gagal atau data OFDB telat masuk, hari berikutnya otomatis
# menghitung ulang tanpa perlu backfill manual.
#
# Kenapa dini hari: perhitungan availability memakai batas hari penuh
# (00:00-24:00), jadi angka satu hari baru final setelah lewat tengah malam.

set -euo pipefail

SUMBER="${1:-berdata}"
if [[ "$SUMBER" != "berdata" && "$SUMBER" != "kinerja" ]]; then
    echo "Sumber titik tidak dikenal: $SUMBER (pilihan: berdata | kinerja)" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo "Project : $PROJECT_ROOT"
echo "Python  : $PYTHON_BIN"
echo "Sumber  : --titik $SUMBER"
echo

pasang_cron() {
    local nama="$1" jadwal="$2" perintah="$3"
    local baris="$jadwal cd $PROJECT_ROOT && $PYTHON_BIN manage.py $perintah >> $LOG_DIR/$nama.log 2>&1"

    if crontab -l 2>/dev/null | grep -qF "manage.py $nama"; then
        echo "  [skip] $nama — cron sudah terpasang"
        echo "         (hapus dulu lewat 'crontab -e' kalau mau ganti opsinya)"
    else
        (crontab -l 2>/dev/null || true; echo "$baris") | crontab -
        echo "  [+] $nama"
        echo "      $baris"
    fi
}

pasang_cron sync_kinerja_analog  "10 1 * * *" "sync_kinerja_analog  --days 3 --titik $SUMBER"
pasang_cron sync_kinerja_digital "20 1 * * *" "sync_kinerja_digital --days 3 --titik $SUMBER"
pasang_cron sync_rc              "30 1 * * *" "sync_rc --days 3"

echo
echo "Crontab sekarang:"
crontab -l 2>/dev/null | grep -E "sync_kinerja|sync_rc" || echo "  (kosong?)"

cat <<EOF

Selesai. Catatan:
  - Log per command ada di $LOG_DIR/ (sync_kinerja_analog.log, dst).
  - Cek besok pagi: tail -n 20 $LOG_DIR/sync_kinerja_analog.log
    Baris normalnya: "[TELEMETERING] <tanggal> titik=<n> avail=<x>% 0%=<n> dilewati=<n>"
  - Kalau angkanya mencurigakan: python manage.py cek_kinerja_ofdb
  - Backfill manual kapan saja, mis. 90 hari ke belakang:
      python manage.py sync_kinerja_analog --days 90 --titik $SUMBER
EOF
