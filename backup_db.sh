#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# backup_db.sh — Backup PostgreSQL database FASOP
# Jalankan dari root project: bash backup_db.sh
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Load .env ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: File .env tidak ditemukan di $SCRIPT_DIR"
    exit 1
fi

# Parse key=value dari .env (abaikan baris komentar dan kosong)
while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    # Hapus kutip di awal/akhir value
    value="${value%\'}"
    value="${value#\'}"
    value="${value%\"}"
    value="${value#\"}"
    export "$key=$value"
done < "$ENV_FILE"

# ── Ambil kredensial ───────────────────────────────────────────────────
DB_NAME="${DB_NAME:?DB_NAME tidak ditemukan di .env}"
DB_USER="${DB_USER:?DB_USER tidak ditemukan di .env}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD tidak ditemukan di .env}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# ── Direktori backup ───────────────────────────────────────────────────
BACKUP_DIR="$SCRIPT_DIR/backups"
mkdir -p "$BACKUP_DIR"

# ── Nama file backup ───────────────────────────────────────────────────
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_FILE="$BACKUP_DIR/fasop_${TIMESTAMP}.sql.gz"

echo "╔══════════════════════════════════════════════════╗"
echo "  FASOP — Backup Database"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Database : $DB_NAME"
echo "  Host     : $DB_HOST:$DB_PORT"
echo "  User     : $DB_USER"
echo "  Output   : $BACKUP_FILE"
echo ""

# ── Jalankan pg_dump ───────────────────────────────────────────────────
PGPASSWORD="$DB_PASSWORD" pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=plain \
    --no-owner \
    --no-acl \
    | gzip > "$BACKUP_FILE"

SIZE="$(du -sh "$BACKUP_FILE" | cut -f1)"
echo "  ✓ Backup selesai — $SIZE"
echo ""

# ── Hapus backup lebih dari 30 hari ───────────────────────────────────
OLD_COUNT=$(find "$BACKUP_DIR" -name "fasop_*.sql.gz" -mtime +30 | wc -l)
if [[ "$OLD_COUNT" -gt 0 ]]; then
    find "$BACKUP_DIR" -name "fasop_*.sql.gz" -mtime +30 -delete
    echo "  ✓ $OLD_COUNT backup lama (>30 hari) dihapus"
fi

# ── Daftar backup yang ada ─────────────────────────────────────────────
echo ""
echo "  Backup tersimpan di $BACKUP_DIR:"
ls -lh "$BACKUP_DIR"/fasop_*.sql.gz 2>/dev/null | awk '{print "    " $5 "  " $9}' || true
echo ""
echo "  Untuk restore:"
echo "    gunzip -c $BACKUP_FILE | psql -h $DB_HOST -U $DB_USER $DB_NAME"
echo ""
