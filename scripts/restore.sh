#!/usr/bin/env bash
# Restore a backup made by backup.sh into a NEW database (never overwrites an existing one).
# Usage: ./scripts/restore.sh backups/<db>-<timestamp> [new_dbname]
set -euo pipefail
cd "$(dirname "$0")/.."

DIR="${1:?usage: ./scripts/restore.sh <backup-dir> [new_dbname]}"
ORIG="$(cat "$DIR/dbname")"
DB="${2:-$ORIG}"

if docker compose exec -T db psql -U odoo -d postgres -Atc "select 1 from pg_database where datname='$DB'" | grep -q 1; then
  echo "Database '$DB' already exists. Pick another name: ./scripts/restore.sh $DIR <new_dbname>" >&2
  exit 1
fi

docker compose exec -T db createdb -U odoo "$DB"
docker compose exec -T db pg_restore -U odoo -d "$DB" --no-owner < "$DIR/db.dump"

if [ -f "$DIR/filestore.tar.gz" ]; then
  docker compose exec -T odoo mkdir -p /var/lib/odoo/filestore
  docker compose exec -T odoo tar -C /var/lib/odoo/filestore --transform "s,^$ORIG,$DB," -xzf - < "$DIR/filestore.tar.gz"
fi

echo "Restored '$ORIG' as '$DB'. Open http://localhost:8069/web?db=$DB"
