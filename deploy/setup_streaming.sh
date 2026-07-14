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
#   2b. Cek apakah ffmpeg terinstal (dipakai transcode rekaman VP8 -> H.264,
#       lihat runOnReady di deploy/mediamtx.yml — TIDAK diinstal otomatis)
#   3. Render deploy/mediamtx.yml (template) -> deploy/mediamtx.generated.yml
#      (config siap pakai, secret sudah terisi — JANGAN pernah commit file ini)
#   4. Pasang cron harian untuk manage.py purge_old_recordings
#
# Yang TETAP HARUS diisi manual — dicetak di akhir script ini:
#   - TURN server (coturn): belum ada di repo ini sama sekali, infrastruktur
#     terpisah yang perlu disiapkan sendiri.
#   - ffmpeg: `sudo apt install -y ffmpeg` kalau belum ada (dicek di atas).
#   - MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL: alamat publik MediaMTX.
#   - webrtcAllowOrigins, TLS (webrtcEncryption) untuk production.
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
echo "  [ok] $RECORDINGS_ROOT siap (dibuat sebagai user $(whoami))"
echo "  [!] Direktori ini dibuat sebagai user $(whoami), tapi MediaMTX kemungkinan"
echo "      jalan sebagai user LAIN (lihat User= di mediamtx.service, langkah 4)."
echo "      Kalau beda, WAJIB jalankan setelah mediamtx.service diisi:"
echo "        sudo chown -R <user-mediamtx>:<group-mediamtx> $RECORDINGS_ROOT"
echo "      Tanpa ini, rekaman gagal DIAM-DIAM (live streaming tetap normal,"
echo "      cuma rekamannya yang tidak pernah tersimpan — cek journalctl -u mediamtx"
echo "      untuk error 'permission denied' kalau curiga)."

echo
echo "=== 2b/4: Cek ffmpeg (dipakai transcode rekaman VP8 -> H.264) ==="
if command -v ffmpeg >/dev/null 2>&1; then
    echo "  [ok] ffmpeg ditemukan: $(command -v ffmpeg)"
else
    echo "  [!] ffmpeg BELUM terinstal — rekaman akan gagal total (bukan cuma"
    echo "      audio-only, prosesnya sama sekali tidak jalan tanpa ffmpeg)."
    echo "      Install dulu:  sudo apt update && sudo apt install -y ffmpeg"
fi

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
echo "=== 3b/4: Render deploy/mediamtx.service.generated ==="
SERVICE_TEMPLATE="$SCRIPT_DIR/mediamtx.service"
SERVICE_OUTPUT="$SCRIPT_DIR/mediamtx.service.generated"
sed "s#/GANTI/PATH/KE/REPO/FASOP/deploy/mediamtx.generated.yml#$OUTPUT#" \
    "$SERVICE_TEMPLATE" > "$SERVICE_OUTPUT"
echo "  [ok] ditulis ke $SERVICE_OUTPUT — path ExecStart sudah otomatis benar ($OUTPUT)."
echo "       Pakai file INI untuk systemd, bukan deploy/mediamtx.service (itu masih template)."

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
echo "    Kalau server di belakang NAT (on-premise): minta tim jaringan teruskan"
echo "    TCP 443, UDP 3478, UDP 49152-49251 dari IP publik ke IP privat server ini."
echo "    (Port MediaMTX 8189 SENGAJA tidak perlu dibuka — semua media dipaksa"
echo "    lewat TURN relay, lihat deploy/turnserver.conf.example.)"
echo ""
echo " 2. TLS untuk MediaMTX (kalau domain+cert FASOP sudah ada, pakai opsi B ini):"
echo "    -> Setup nginx reverse-proxy ke MediaMTX pakai domain+cert yang sudah"
echo "       ada — lihat panduan lengkap di deploy/nginx-mediamtx.conf.example"
echo "       (perlu subdomain baru, mis. media.domain-anda, + sertifikatnya)."
echo "    -> Lalu $ENV_FILE -> MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL diisi"
echo "       https://media.domain-anda (BUKAN localhost/127.0.0.1)."
echo "    -> Lalu $OUTPUT -> webrtcAllowOrigins diisi origin Django FASOP"
echo "       (mis. https://fasop.domain-anda, BUKAN domain media-nya)."
echo ""
echo " 3. authHTTPAddress & runOnRecordSegmentComplete di $OUTPUT"
echo "    -> Kalau MediaMTX & Django di SERVER YANG SAMA: 127.0.0.1:8000 sudah"
echo "       benar, tidak perlu diubah."
echo "    -> Kalau di server TERPISAH: ganti ke alamat Django yang benar, dan"
echo "       pastikan STREAMING_RECORDINGS_ROOT bisa diakses kedua server"
echo "       (shared mount, bukan folder lokal)."
echo ""
echo " 4. Pasang sebagai systemd service pakai HASIL GENERATE ($SERVICE_OUTPUT):"
echo "      sudo cp $SERVICE_OUTPUT /etc/systemd/system/mediamtx.service"
echo "      sudo nano /etc/systemd/system/mediamtx.service   # cek/isi User & Group saja, ExecStart sudah benar"
echo "      sudo systemctl daemon-reload"
echo "      sudo systemctl enable --now mediamtx"
echo "════════════════════════════════════════════════════════════════════"
