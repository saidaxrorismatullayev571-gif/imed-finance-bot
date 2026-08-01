#!/usr/bin/env bash
# Zaxira nusxasidan bazani tiklaydi.
# DIQQAT: bu joriy bazadagi BARCHA ma'lumotni zaxiradagisi bilan
# ALMASHTIRADI — bu amalni ORQAGA QAYTARIB BO'LMAYDI.
#
# Foydalanish: ./scripts/restore.sh backups/imed_finance_20260717_030000.sql.gz

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

DB_USER="${POSTGRES_USER:-imed}"
DB_NAME="${POSTGRES_DB:-imed_finance}"
FILE="${1:-}"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
    echo "Foydalanish: $0 <zaxira-fayli.sql.gz>" >&2
    exit 1
fi

echo "DIQQAT: bu '$DB_NAME' bazasidagi BARCHA joriy ma'lumotni"
echo "'$FILE' fayli bilan ALMASHTIRADI. Bu amalni orqaga qaytarib bo'lmaydi."
read -r -p "Davom etasizmi? Tasdiqlash uchun 'ha' deb yozing: " CONFIRM
if [ "$CONFIRM" != "ha" ]; then
    echo "Bekor qilindi."
    exit 0
fi

gunzip -c "$FILE" | docker compose exec -T db psql -U "$DB_USER" "$DB_NAME"
echo "[$(date '+%F %T')] Zaxiradan tiklandi: $FILE"
