#!/usr/bin/env bash
# =============================================================================
# One-command bootstrap: build the identical Vela Tech store from git.
#
#   ./scripts/setup.sh              # new machine: config + containers + CommercePulse
#   ./scripts/setup.sh vela_test    # (re)build a throwaway DB the same way (CLI only)
#
# What it does (idempotent, safe to re-run):
#   1. creates .env and config/odoo.conf from the templates if missing (random secrets)
#   2. pulls the pinned images, starts Postgres
#   3. creates the DB exactly like the web form (country TN, en_US) if it doesn't exist
#   4. installs vela_setup = every app + our addons + shared settings + catalog
#   5. starts Odoo and checks the site answers
# Existing DB? It is NOT touched: use ./scripts/update.sh instead.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

DB="${1:-CommercePulse}"
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# --- 1. local config ---------------------------------------------------------
if [ ! -f .env ]; then
  if docker volume inspect "$(basename "$PWD")_odoo-db-data" >/dev/null 2>&1; then
    echo "A database volume already exists but .env is missing." >&2
    echo "Recreate .env with the password that volume was created with (see .env.example)." >&2
    exit 1
  fi
  say "Creating .env (random DB password)"
  sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" \
      -e "s/^VELA_BRIDGE_TOKEN=.*/VELA_BRIDGE_TOKEN=$(openssl rand -hex 24)/" .env.example > .env
fi
if [ ! -f config/odoo.conf ]; then
  say "Creating config/odoo.conf (random master password)"
  pw="$(openssl rand -base64 24 | tr -d '/+=')"
  sed "s/^admin_passwd = .*/admin_passwd = ${pw}/" config/odoo.conf.example > config/odoo.conf
  echo "Database-manager master password: ${pw}   (save it; it is only in config/odoo.conf)"
fi

# --- 2. containers ------------------------------------------------------------
PGUSER_="$(grep ^POSTGRES_USER .env | cut -d= -f2)"
PGPASS_="$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2)"

say "Pulling pinned images and starting Postgres"
docker compose pull -q
docker compose up -d db
until docker compose exec -T db pg_isready -U "$PGUSER_" >/dev/null 2>&1; do sleep 1; done

# --- 3. database --------------------------------------------------------------
exists="$(docker compose exec -T db psql -U "$PGUSER_" -d postgres -Atc \
  "select 1 from pg_database where datname='${DB}'")"
if [ "$exists" = "1" ]; then
  say "Database ${DB} already exists. Leaving it alone (use ./scripts/update.sh)"
else
  say "Creating database ${DB} (country TN, en_US, no demo data)"
  [ "$DB" = "CommercePulse" ] && docker compose stop odoo >/dev/null 2>&1 || true
  # bypass the image entrypoint: it appends --db_* flags after the subcommand,
  # which `odoo db` rejects. Connection flags must come before `init`.
  docker compose run --rm --no-deps --entrypoint odoo odoo db -c /etc/odoo/odoo.conf \
    --db_host db -r "$PGUSER_" -w "$PGPASS_" \
    init "$DB" --country TN --language en_US

  # --- 4. the whole store -----------------------------------------------------
  say "Installing vela_setup (apps + addons + settings + catalog). Takes a few minutes"
  docker compose run --rm --no-deps odoo odoo -d "$DB" -i vela_setup --stop-after-init \
    2>&1 | grep -E "ERROR|CRITICAL|Traceback|vela_setup:|Vela Tech catalog" || true
  state="$(docker compose exec -T db psql -U "$PGUSER_" -d "$DB" -Atc \
    "select state from ir_module_module where name='vela_setup'")"
  if [ "$state" != "installed" ]; then
    echo "vela_setup did not install (state: ${state:-missing}). See the errors above." >&2
    exit 1
  fi
fi

# --- 5. start + check -----------------------------------------------------------
if [ "$DB" = "CommercePulse" ]; then
  say "Starting Odoo"
  docker compose up -d odoo
  for _ in $(seq 1 30); do
    code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8069/shop || true)"
    [ "$code" = "200" ] && break; sleep 2
  done
  echo "Store: http://localhost:8069/shop (HTTP ${code})"
  echo "Back-office login: admin / admin  (change it: Settings > Users)"
fi
./scripts/drift.sh "$DB" || true
