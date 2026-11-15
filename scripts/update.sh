#!/usr/bin/env bash
# =============================================================================
# Bring your database in line with the code after `git pull`.
#
#   ./scripts/update.sh               # CommercePulse
#   ./scripts/update.sh vela_test     # test DB (server keeps running)
#
# Upgrades every addon in addons/ that is installed, and installs vela_setup's
# new dependencies (an app a teammate added to its manifest gets installed here).
# Fails loudly (exit 1, full error shown) if Odoo can't load the upgraded code.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

DB="${1:-CommercePulse}"
mods="$(find addons -maxdepth 2 -name __manifest__.py -printf '%h\n' | xargs -n1 basename | sort | paste -sd, -)"
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
echo "Upgrading on ${DB}: ${mods}"

[ "$DB" = "CommercePulse" ] && docker compose stop odoo >/dev/null
docker compose run --rm --no-deps odoo odoo -d "$DB" -u "$mods" --stop-after-init >"$log" 2>&1
[ "$DB" = "CommercePulse" ] && docker compose start odoo >/dev/null

if grep -qE "CRITICAL|Failed to load registry|Traceback" "$log"; then
  echo "UPGRADE FAILED on ${DB}. Odoo kept the previous state. Error:" >&2
  grep -E -A14 "Error while|Traceback|CRITICAL" "$log" | grep -vE '^\s+\^+$' | head -40 >&2
  exit 1
fi
grep -E "WARNING|ERROR" "$log" | grep -vE "markdown2|unknown module" | head -20
grep "vela_setup:" "$log" | tail -1

./scripts/drift.sh "$DB" || true
