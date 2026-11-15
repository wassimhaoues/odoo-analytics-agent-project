#!/usr/bin/env bash
# =============================================================================
# Detect state that exists in a database but not in git (so a teammate won't have it).
#
#   ./scripts/drift.sh [db]            # default CommercePulse
#   ./scripts/drift.sh CommercePulse vela_test   # also diff installed modules of two DBs
#
# Checks:
#   - apps installed by hand: installed, nothing depends on them, not auto-install,
#     and not listed in addons/vela_setup/__manifest__.py
#   - our addons in addons/ that are not installed
#   - (two DBs) modules installed in one DB but not the other
# Exit 1 when drift is found.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

DB="${1:-CommercePulse}"
OTHER="${2:-}"
USER_="$(grep ^POSTGRES_USER .env | cut -d= -f2)"
q() { docker compose exec -T db psql -U "$USER_" -d "$1" -Atc "$2"; }

declared="$(python3 - <<'EOF'
import ast, pathlib
m = ast.literal_eval(pathlib.Path("addons/vela_setup/__manifest__.py").read_text())
print("\n".join(m["depends"] + ["vela_setup"]))
EOF
)"
drift=0

manual="$(q "$DB" "select m.name from ir_module_module m
  where m.state='installed' and not m.auto_install
    and not exists (select 1 from ir_module_module_dependency d
                    join ir_module_module m2 on m2.id=d.module_id and m2.state='installed'
                    where d.name=m.name)
  order by 1" | grep -vxF -f <(echo "$declared") || true)"
if [ -n "$manual" ]; then
  drift=1
  echo "DRIFT [$DB] apps installed but not declared in vela_setup/__manifest__.py depends:"
  echo "$manual" | sed 's/^/  - /'
fi

ours="$(find addons -maxdepth 2 -name __manifest__.py -printf '%h\n' | xargs -n1 basename | sort)"
installed="$(q "$DB" "select name from ir_module_module where state='installed'")"
missing="$(echo "$ours" | grep -vxF -f <(echo "$installed") || true)"
if [ -n "$missing" ]; then
  drift=1
  echo "DRIFT [$DB] our addons not installed (add to vela_setup depends, then update.sh):"
  echo "$missing" | sed 's/^/  - /'
fi

if [ -n "$OTHER" ]; then
  a="$(q "$DB" "select name from ir_module_module where state='installed' order by 1")"
  b="$(q "$OTHER" "select name from ir_module_module where state='installed' order by 1")"
  d="$(diff <(echo "$a") <(echo "$b") | grep -E '^[<>]' || true)"
  if [ -n "$d" ]; then
    drift=1
    echo "DIFF installed modules  (< only in $DB, > only in $OTHER):"
    echo "$d" | sed 's/^/  /'
  fi
fi

[ "$drift" = 0 ] && echo "No drift: $DB matches what git declares."
exit "$drift"
