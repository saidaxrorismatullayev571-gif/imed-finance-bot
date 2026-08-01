#!/usr/bin/env bash
# Postgres bazasining siqilgan zaxira nusxasini oladi va eski nusxalarni
# tozalaydi. docker-compose orqali ishlaydi (server, prod muhit).
#
# Foydalanish:   ./scripts/backup.sh
# Cron misoli:   0 3 * * * cd /path/to/imed-finance-bot && ./scripts/backup.sh >> /var/log/imed-backup.log 2>&1
#
# Muhit o'zgaruvchilari (ixtiyoriy, docker-compose.yml dagi standartlarga mos):
#   BACKUP_DIR       — zaxiralar saqlanadigan papka (standart: ./backups)
#   BACKUP_KEEP_DAYS — necha kunlik zaxira saqlanadi (standart: 30)
#   POSTGRES_USER, POSTGRES_DB — docker-compose.yml dagi qiymatlarga mos bo'lishi shart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
DB_USER="${POSTGRES_USER:-imed}"
DB_NAME="${POSTGRES_DB:-imed_finance}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILE="$BACKUP_DIR/imed_finance_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date '+%F %T')] Zaxira boshlandi: $FILE"
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$FILE"

if [ ! -s "$FILE" ]; then
    echo "[$(date '+%F %T')] XATO: zaxira fayli bo'sh yoki yaratilmadi!" >&2
    rm -f "$FILE"
    exit 1
fi

echo "[$(date '+%F %T')] Zaxira tayyor: $FILE ($(du -h "$FILE" | cut -f1))"

find "$BACKUP_DIR" -name "imed_finance_*.sql.gz" -mtime "+${KEEP_DAYS}" -print -delete
echo "[$(date '+%F %T')] ${KEEP_DAYS} kundan eski zaxiralar tozalandi"
