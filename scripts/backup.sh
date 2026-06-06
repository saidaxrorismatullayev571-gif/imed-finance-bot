#!/bin/sh
# Kunlik PostgreSQL backup (pg_dump). docker-compose `backup` xizmati ishlatadi.
# So'nggi 14 nusxa saqlanadi, eskilari o'chiriladi.
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP="${BACKUP_KEEP:-14}"
INTERVAL="${BACKUP_INTERVAL:-86400}"   # soniya (sukut: 24 soat)

mkdir -p "$BACKUP_DIR"

while true; do
    ts=$(date +%F_%H%M)
    out="$BACKUP_DIR/imed_$ts.sql"
    echo "[backup] $ts -> $out"
    if pg_dump "$DATABASE_URL" > "$out"; then
        gzip -f "$out"
        echo "[backup] muvaffaqiyatli: $out.gz"
    else
        echo "[backup] XATO: pg_dump ishlamadi"
        rm -f "$out"
    fi
    # eski nusxalarni tozalash (so'nggi $KEEP dan boshqasi)
    ls -1t "$BACKUP_DIR"/imed_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
    sleep "$INTERVAL"
done
