#!/usr/bin/env bash
# Back up one Odoo database + its filestore into ./backups/<db>-<timestamp>/
# Usage: ./scripts/backup.sh <dbname>
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:?usage: ./scripts/backup.sh <dbname>}"
OUT="backups/${DB}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

echo "$DB" > "$OUT/dbname"
docker compose exec -T db pg_dump -U odoo -Fc "$DB" > "$OUT/db.dump"

if docker compose exec -T odoo test -d "/var/lib/odoo/filestore/$DB"; then
  docker compose exec -T odoo tar -C /var/lib/odoo/filestore -czf - "$DB" > "$OUT/filestore.tar.gz"
else
  echo "(no filestore yet for $DB, skipped)"
fi

echo "Backup done: $OUT"
ls -lh "$OUT"
