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
#   2c. Cek FASOP_PUBLIC_ORIGIN & TURN_URL/TURN_USERNAME/TURN_PASSWORD di
#       .env, salin ke mediamtx.generated.yml kalau ada
#   3. Render deploy/mediamtx.yml (template) -> deploy/mediamtx.generated.yml
#      (config siap pakai, secret & (kalau sudah diisi) origin/TURN sudah
#      terisi — JANGAN pernah commit file ini)
#   4. Pasang cron harian untuk manage.py purge_old_recordings
#
# PENTING: mediamtx.generated.yml di-generate ULANG DARI NOL tiap script ini
# jalan. JANGAN PERNAH edit file itu secara manual langsung — isi apapun
# yang perlu beda dari template WAJIB lewat .env (FASOP_PUBLIC_ORIGIN,
# TURN_URL, dst di atas), supaya tidak hilang lagi kalau script ini
# dijalankan ulang di kemudian hari (pernah kejadian: origin & TURN yang
# diisi manual ke mediamtx.generated.yml hilang tertimpa placeholder lagi
# setelah re-run, live streaming gagal CORS/TURN tanpa pesan jelas).
#
# Yang TETAP HARUS diisi manual — dicetak di akhir script ini:
#   - TURN server (coturn): belum ada di repo ini sama sekali, infrastruktur
#     terpisah yang perlu disiapkan sendiri. Setelah coturn jalan, isi
#     kredensialnya ke .env (TURN_URL/TURN_USERNAME/TURN_PASSWORD +
#     WEBRTC_ICE_SERVERS), BUKAN ke mediamtx.generated.yml langsung.
#   - ffmpeg: `sudo apt install -y ffmpeg` kalau belum ada (dicek di atas).
#   - MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL: alamat publik MediaMTX.
#   - FASOP_PUBLIC_ORIGIN di .env, TLS (webrtcEncryption) untuk production.
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
echo "=== 2c/4: Origin & TURN untuk MediaMTX (FASOP_PUBLIC_ORIGIN, TURN_URL, TURN_USERNAME, TURN_PASSWORD) ==="
# PENTING: mediamtx.generated.yml di-generate ULANG DARI NOL setiap script
# ini dijalankan — kalau nilai-nilai ini pernah diisi manual langsung di
# mediamtx.generated.yml (bukan di .env), isian itu HILANG tertimpa
# placeholder lagi tiap re-run, dan live streaming langsung gagal CORS /
# TURN tidak connect tanpa pesan yang jelas. Makanya wajib lewat .env di
# sini supaya idempotent.
ORIGIN="$(get_env FASOP_PUBLIC_ORIGIN || true)"
TURN_URL="$(get_env TURN_URL || true)"
TURN_USERNAME="$(get_env TURN_USERNAME || true)"
TURN_PASSWORD="$(get_env TURN_PASSWORD || true)"

if [[ -n "$ORIGIN" ]]; then
    echo "  [ok] FASOP_PUBLIC_ORIGIN = $ORIGIN"
else
    echo "  [!] FASOP_PUBLIC_ORIGIN belum ada di .env — webrtcAllowOrigins akan"
    echo "      tetap placeholder, live streaming GAGAL (CORS) sampai diisi."
    echo "      Tambahkan ke .env, contoh: FASOP_PUBLIC_ORIGIN=https://fasopup2bmks.id"
fi
if [[ -n "$TURN_URL" && -n "$TURN_USERNAME" && -n "$TURN_PASSWORD" ]]; then
    echo "  [ok] TURN_URL/TURN_USERNAME/TURN_PASSWORD ada di .env"
else
    echo "  [!] TURN_URL/TURN_USERNAME/TURN_PASSWORD belum lengkap di .env —"
    echo "      webrtcICEServers2 (TURN) akan tetap placeholder, HP teknisi di"
    echo "      lapangan (CGNAT) GAGAL connect sampai diisi."
    echo "      Tambahkan ke .env, contoh:"
    echo "        TURN_URL=turn:202.65.235.144:3478"
    echo "        TURN_USERNAME=fasop"
    echo "        TURN_PASSWORD=<sama persis dengan user= di /etc/turnserver.conf>"
fi

echo
echo "=== 3/4: Render deploy/mediamtx.generated.yml ==="
TEMPLATE="$SCRIPT_DIR/mediamtx.yml"
OUTPUT="$SCRIPT_DIR/mediamtx.generated.yml"
SED_ARGS=(
    -e "s#isi-MEDIAMTX_AUTH_SECRET-yang-sama-dengan-env-django#${SECRET}#g"
    -e "s#/var/lib/fasop-streaming/recordings#${RECORDINGS_ROOT}#g"
)
if [[ -n "$ORIGIN" ]]; then
    SED_ARGS+=(-e "s#isi-FASOP_PUBLIC_ORIGIN-yang-sama-dengan-env-django#${ORIGIN}#g")
fi
if [[ -n "$TURN_URL" && -n "$TURN_USERNAME" && -n "$TURN_PASSWORD" ]]; then
    SED_ARGS+=(
        -e "s#isi-TURN_URL-yang-sama-dengan-env-django#${TURN_URL}#g"
        -e "s#isi-TURN_USERNAME-yang-sama-dengan-env-django#${TURN_USERNAME}#g"
        -e "s#isi-TURN_PASSWORD-yang-sama-dengan-env-django#${TURN_PASSWORD}#g"
    )
fi
sed "${SED_ARGS[@]}" "$TEMPLATE" > "$OUTPUT"
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
echo "    yang SAMA PERSIS di 3 tempat DI .env (BUKAN langsung di $OUTPUT —"
echo "    lihat catatan di kepala script ini kenapa):"
echo "      - $ENV_FILE -> WEBRTC_ICE_SERVERS (dipakai browser)"
echo "      - $ENV_FILE -> TURN_URL, TURN_USERNAME, TURN_PASSWORD (dipakai MediaMTX,"
echo "        disalin otomatis ke webrtcICEServers2 tiap script ini dijalankan)"
echo "    Kalau server di belakang NAT (on-premise): minta tim jaringan teruskan"
echo "    TCP 443, UDP 3478, UDP 49152-49251 dari IP publik ke IP privat server ini."
echo "    (Port MediaMTX 8189 SENGAJA tidak perlu dibuka — semua media dipaksa"
echo "    lewat TURN relay, lihat deploy/turnserver.conf.example.)"
echo "    Kalau ORIGIN/TURN_* di atas tadi tercetak [!] (belum lengkap), isi"
echo "    dulu di .env lalu JALANKAN ULANG script ini sebelum restart mediamtx."
echo ""
echo " 2. TLS untuk MediaMTX (kalau domain+cert FASOP sudah ada, pakai opsi B ini):"
echo "    -> Setup nginx reverse-proxy ke MediaMTX pakai domain+cert yang sudah"
echo "       ada — lihat panduan lengkap di deploy/nginx-mediamtx.conf.example"
echo "       (perlu subdomain baru, mis. media.domain-anda, + sertifikatnya)."
echo "    -> Lalu $ENV_FILE -> MEDIAMTX_WHIP_URL / MEDIAMTX_WHEP_URL diisi"
echo "       https://media.domain-anda (BUKAN localhost/127.0.0.1)."
echo "    -> Lalu $ENV_FILE -> FASOP_PUBLIC_ORIGIN diisi origin Django FASOP"
echo "       (mis. https://fasop.domain-anda, BUKAN domain media-nya) —"
echo "       JALANKAN ULANG script ini setelah ini biar webrtcAllowOrigins terisi."
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
