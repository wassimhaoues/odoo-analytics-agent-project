#!/usr/bin/env bash
# Tests for bash-guard.sh. Run: .claude/hooks/bash-guard.test.sh
set -uo pipefail
guard="$(dirname "$0")/bash-guard.sh"
fail=0

run() { python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]}}))' "$1" | "$guard" 2>/dev/null; echo $?; }
expect() { local want="$1" cmd="$2" got; got="$(run "$cmd")"
  if [ "$got" = "$want" ]; then echo "ok   [$want] $cmd"; else echo "FAIL [want $want got $got] $cmd"; fail=1; fi; }

# must block (2)
expect 2 "docker compose exec -T db dropdb -U odoo CommercePulse"
expect 2 "psql -c 'DROP DATABASE \"CommercePulse\"'"
expect 2 "docker compose down -v"
expect 2 "docker volume rm odoo-study_odoo-db-data"
expect 2 "docker volume prune -f"
expect 2 "docker stop customer-postgres"
expect 2 "rm -rf addons"
expect 2 "rm -rf .git"
expect 2 "git push --force origin main"
expect 2 "git push origin main -f"
expect 2 "git add -f .env"
expect 2 "git add .env"
expect 2 "git add config/odoo.conf"
# must allow (0)
expect 0 "docker compose exec -T db dropdb -U odoo --if-exists vela_test"
expect 0 "docker compose down"
expect 0 "docker compose restart odoo"
expect 0 "rm -rf addons/vela_tech_catalog/static/img/products/VT-TST-001.jpg"
expect 0 "rm -rf scripts/catalog/.cache"
expect 0 "git push origin feat/theme-vela"
expect 0 "git add .env.example config/odoo.conf.example"
expect 0 "docker compose run --rm --no-deps odoo odoo -d CommercePulse -u vela_tech_catalog --stop-after-init"

exit $fail
