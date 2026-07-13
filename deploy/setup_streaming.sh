#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# setup_streaming.sh — Setup & re-check operasional fitur Live Streaming
# (MediaMTX). Jalankan dari root project: bash deploy/setup_streaming.sh
#
# Aman dijalankan berulang kali (idempotent) — pakai ini kapan pun ragu
# apakah setup live streaming di server ini sudah lengkap.
#
# Yang DIKERJAKAN OTOMATIS oleh script ini:
#   1. Generate MEDIAMTX_AUTH_SECRET (kalau belum ada di .env)
#   2. Siapkan STREAMING_RECORDINGS_ROOT (buat direktori kalau belum ada)
#   3. Render deploy/mediamtx.yml (template) -> deploy/mediamtx.generated.yml
#      (config siap pakai, secret sudah terisi — JANGAN pernah commit file ini)
#   4. Pasang cron harian untuk manage.py purge_old_recordings
#
# Yang TETAP HARUS diisi manual — dicetak di akhir script ini:
#   - TURN server (coturn): belum ada di repo ini sama sekali, infrastruktur
#     terpisah yang perlu disiapkan sendiri.
#   - MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL: alamat publik MediaMTX.
#   - webrtcAllowOrigin, TLS (webrtcEncryption) untuk production.
#   - authHTTPAddress / runOnRecordSegmentComplete kalau MediaMTX ada di
#     server terpisah dari Django (bukan 127.0.0.1:8000).
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: File .env tidak ditemukan di $PROJECT_ROOT — buat dulu (lihat CLAUDE.md bagian Environment Variables) sebelum jalankan script ini."
    exit 1
fi

get_env() {
    grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d '=' -f2-
}

set_env() {
    local key="$1" value="$2"
    if grep -qE "^$key=" "$ENV_FILE"; then
        echo "  [skip] $key sudah ada di .env"
    else
        echo "$key=$value" >> "$ENV_FILE"
        echo "  [+] $key ditambahkan ke .env"
    fi
}

echo "=== 1/4: MEDIAMTX_AUTH_SECRET ==="
SECRET="$(get_env MEDIAMTX_AUTH_SECRET || true)"
if [[ -z "$SECRET" ]]; then
    SECRET="$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(32))')"
    set_env "MEDIAMTX_AUTH_SECRET" "$SECRET"
else
    echo "  [skip] sudah ada di .env"
fi

echo
echo "=== 2/4: Direktori rekaman (STREAMING_RECORDINGS_ROOT) ==="
RECORDINGS_ROOT="$(get_env STREAMING_RECORDINGS_ROOT || true)"
if [[ -z "$RECORDINGS_ROOT" ]]; then
    RECORDINGS_ROOT="$PROJECT_ROOT/streaming_recordings"
    set_env "STREAMING_RECORDINGS_ROOT" "$RECORDINGS_ROOT"
fi
mkdir -p "$RECORDINGS_ROOT"
echo "  [ok] $RECORDINGS_ROOT siap"
echo "  [!] pastikan user yang menjalankan MediaMTX bisa MENULIS ke sini,"
echo "      dan user yang menjalankan gunicorn bisa MEMBACA-nya."

echo
echo "=== 3/4: Render deploy/mediamtx.generated.yml ==="
TEMPLATE="$SCRIPT_DIR/mediamtx.yml"
OUTPUT="$SCRIPT_DIR/mediamtx.generated.yml"
sed \
    -e "s#isi-MEDIAMTX_AUTH_SECRET-yang-sama-dengan-env-django#${SECRET}#g" \
    -e "s#/var/lib/fasop-streaming/recordings#${RECORDINGS_ROOT}#g" \
    "$TEMPLATE" > "$OUTPUT"
echo "  [ok] ditulis ke $OUTPUT (sudah di-gitignore — jangan pernah commit, berisi secret)"

echo
echo "=== 4/4: Cron retensi rekaman (purge_old_recordings, harian 03:00) ==="
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(command -v python3)"
mkdir -p "$PROJECT_ROOT/logs"
CRON_LINE="0 3 * * * cd $PROJECT_ROOT && $PYTHON_BIN manage.py purge_old_recordings >> $PROJECT_ROOT/logs/purge_old_recordings.log 2>&1"
if crontab -l 2>/dev/null | grep -qF "purge_old_recordings"; then
    echo "  [skip] cron sudah terpasang"
else
    (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
    echo "  [+] cron ditambahkan: $CRON_LINE"
fi

echo
echo "════════════════════════════════════════════════════════════════════"
echo " SELESAI BAGIAN OTOMATIS. Yang MASIH HARUS dicek/diisi MANUAL:"
echo "════════════════════════════════════════════════════════════════════"
echo " 1. TURN server (coturn) — WAJIB untuk HP teknisi di lapangan (CGNAT)."
echo "    Cek dulu apa sudah ada: which turnserver ; systemctl status coturn"
echo "    Kalau belum ada, install dulu. Setelah coturn jalan, isi kredensial"
echo "    yang SAMA PERSIS di 2 tempat:"
echo "      - $ENV_FILE                 -> WEBRTC_ICE_SERVERS"
echo "      - $OUTPUT -> webrtcICEServers2 (password:)"
echo "    Buka juga port UDP TURN (3478) + port media MediaMTX (webrtcICEUDPMuxAddress, 8189) di firewall."
echo ""
echo " 2. TLS untuk MediaMTX (kalau domain+cert FASOP sudah ada, pakai opsi B ini):"
echo "    -> Setup nginx reverse-proxy ke MediaMTX pakai domain+cert yang sudah"
echo "       ada — lihat panduan lengkap di deploy/nginx-mediamtx.conf.example"
echo "       (perlu subdomain baru, mis. media.domain-anda, + sertifikatnya)."
echo "    -> Lalu $ENV_FILE -> MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL diisi"
echo "       https://media.domain-anda (BUKAN localhost/127.0.0.1)."
echo "    -> Lalu $OUTPUT -> webrtcAllowOrigin diisi origin Django FASOP"
echo "       (mis. https://fasop.domain-anda, BUKAN domain media-nya)."
echo ""
echo " 3. authHTTPAddress & runOnRecordSegmentComplete di $OUTPUT"
echo "    -> Kalau MediaMTX & Django di SERVER YANG SAMA: 127.0.0.1:8000 sudah"
echo "       benar, tidak perlu diubah."
echo "    -> Kalau di server TERPISAH: ganti ke alamat Django yang benar, dan"
echo "       pastikan STREAMING_RECORDINGS_ROOT bisa diakses kedua server"
echo "       (shared mount, bukan folder lokal)."
echo ""
echo " 4. Jalankan MediaMTX pakai HASIL GENERATE, bukan template:"
echo "      ./mediamtx $OUTPUT"
echo "    Sebaiknya sebagai systemd service — lihat deploy/mediamtx.service"
echo "    (isi User/ExecStart di situ dulu, lalu systemctl enable --now)."
echo "════════════════════════════════════════════════════════════════════"
