#!/usr/bin/env bash
#
# setup_freq_rt_cron.sh — pasang cron perekam frekuensi sistem milik FASOP sendiri.
#
# Idempotent: kalau baris cronnya sudah ada, dilewati (tidak dobel). Aman
# dijalankan ulang kapan saja.
#
#   bash deploy/setup_freq_rt_cron.sh          # 1 sampel/detik (disarankan)
#   bash deploy/setup_freq_rt_cron.sh menit    # 1 sampel/menit (hemat, resolusi kasar)
#
# KENAPA INI ADA
#
# Riwayat frekuensi aslinya datang dari SYS_FREQ_HIS di historian SCADA. Job
# penulis tabel itu pernah berhenti berhari-hari tanpa ketahuan (24 Agustus 2026
# pukul 15:17 sampai berhari-hari sesudahnya, didahului beberapa pemadaman
# parsial sejak 19 Agustus). Selama itu SELURUH analisis Respons Pembangkit
# mati, padahal SYS_FREQ_RT (nilai realtime) di server yang sama tetap hidup.
#
# Cron ini membuat FASOP merekam frekuensinya sendiri dari SYS_FREQ_RT ke
# PostgreSQL (opsis.SnapFreqRT), sehingga riwayatnya tidak lagi bergantung pada
# satu job di luar kendali FASOP. opsis/freq_history.py menggabungkan keduanya:
# historian tetap jadi acuan bila ada, rekaman ini menambal lubangnya.
#
# RESOLUSI ITU PENTING, JANGAN DITURUNKAN TANPA SADAR
#
# Respons Pembangkit menganalisis jendela -60/+180 detik di sekitar titik
# ekstrem. Pada 1 sampel/menit jendela itu cuma berisi ~4 titik — ayunan
# frekuensi yang berlangsung 10-20 detik tidak akan terlihat sama sekali.
# SYS_FREQ_HIS memberi 1 sampel/detik (86.400 baris/hari), dan mode default
# skrip ini menyamainya.
#
# BIAYA PENYIMPANAN
#
# 1 sampel/detik = 86.400 baris/hari ~ 8 MB/hari. collect_freq_rt sudah
# menghapus sendiri data di atas 30 hari, jadi mentok di ~240 MB dan tidak
# tumbuh terus.

set -euo pipefail

MODE="${1:-detik}"
if [[ "$MODE" != "detik" && "$MODE" != "menit" ]]; then
    echo "Mode tidak dikenal: $MODE (pilihan: detik | menit)" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo "Project : $PROJECT_ROOT"
echo "Python  : $PYTHON_BIN"
echo "Mode    : $MODE"
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

if [[ "$MODE" == "detik" ]]; then
    # --durasi 55, bukan 60: satu putaran harus selesai sebelum cron berikutnya
    # menyala. Kalaupun tumpang-tindih, SnapFreqRT.waktu unik + get_or_create
    # mencegah duplikat — ini cuma supaya tidak ada proses menumpuk sia-sia.
    pasang_cron collect_freq_rt "* * * * *" "collect_freq_rt --loop --interval 1 --durasi 55"
else
    pasang_cron collect_freq_rt "* * * * *" "collect_freq_rt"
fi

echo
echo "Crontab sekarang:"
crontab -l 2>/dev/null | grep -E "collect_freq_rt" || echo "  (kosong?)"

cat <<EOF

Selesai. Catatan:
  - Log ada di $LOG_DIR/collect_freq_rt.log
  - Cek beberapa menit lagi:
      tail -n 5 $LOG_DIR/collect_freq_rt.log
    Baris normalnya: "Loop 55s @ 1.0s: 55 sampel disimpan."
  - Cek isinya benar-benar masuk:
      python manage.py shell -c "from opsis.models import SnapFreqRT; print(SnapFreqRT.objects.count())"
  - Bedah kolom SYS_FREQ_RT kalau nilainya kosong:
      python manage.py collect_freq_rt --probe
    Bila kolom Hz bukan 'VALUE', set MSSQL_FREQ_RT_COL di .env.

  Rekaman ini TIDAK bisa mengisi masa lalu. Lubang SYS_FREQ_HIS sebelum cron ini
  dipasang hanya bisa dipulihkan dari arsip historian di sisi SCADA.
EOF
