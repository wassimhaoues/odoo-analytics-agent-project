#!/usr/bin/env bash
# =============================================================================
# edit-lint — PostToolUse hook for Edit|Write|MultiEdit
# Fast static checks on the file just written. Never blocks the write (it already
# happened); exit 2 feeds the problem back to the agent so it fixes it now.
#   .py   → py_compile (syntax)
#   .xml  → well-formed XML
#   .json → valid JSON
#   .csv  under security/ → header check for ir.access.csv (Odoo 20)
#   .sh   → bash -n
# =============================================================================
set -uo pipefail

payload="$(cat 2>/dev/null || true)"
file="$(printf '%s' "$payload" | python3 -c 'import json,sys
try:
  d=json.load(sys.stdin); print(d.get("tool_input",{}).get("file_path",""))
except Exception: print("")' 2>/dev/null)"
[ -z "$file" ] || [ ! -f "$file" ] && exit 0
case "$file" in */.claude/skills/ui-ux-pro-max/*|*/node_modules/*) exit 0 ;; esac

err=""
case "$file" in
  *.py)   err="$(python3 -m py_compile "$file" 2>&1)" ;;
  *.xml)  err="$(python3 -c 'import sys,xml.dom.minidom as m; m.parse(sys.argv[1])' "$file" 2>&1)" ;;
  *.json) err="$(python3 -c 'import sys,json; json.load(open(sys.argv[1]))' "$file" 2>&1)" ;;
  *.sh)   err="$(bash -n "$file" 2>&1)" ;;
  */security/ir.model.access.csv)
          err="Odoo 20 has no ir.model.access: use security/ir.access.csv (rules/odoo-addon.md)" ;;
  */security/ir.access.csv)
          head -1 "$file" | grep -q '^id,name,model_id,group_id/id,operation,domain' \
            || err="ir.access.csv header must be: id,name,model_id,group_id/id,operation,domain" ;;
esac

if [ -n "$err" ]; then
  echo "edit-lint: $file has a problem:" >&2
  echo "$err" | tail -5 >&2
  exit 2
fi
exit 0
