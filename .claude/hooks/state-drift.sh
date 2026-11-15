#!/usr/bin/env bash
# =============================================================================
# state-drift — PostToolUse hook for Bash
# After a command that installs Odoo modules or runs the update flow, run
# scripts/drift.sh. If the DB now has state git doesn't declare, tell the agent
# (exit 2 feeds stderr back) so it updates vela_setup before moving on.
# =============================================================================
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

payload="$(cat 2>/dev/null || true)"
cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"

# only after installs on the real DB (-i / --init / module install)
echo "$cmd" | grep -q "CommercePulse" || exit 0
echo "$cmd" | grep -qE "(^|[[:space:]])(-i|--init)([= ][^-]|[[:space:]])|module install" || exit 0
[ -x scripts/drift.sh ] || exit 0

out="$(./scripts/drift.sh CommercePulse 2>&1)" && exit 0
echo "state-drift: CommercePulse now has state that git doesn't declare:" >&2
echo "$out" >&2
echo "Per .claude/rules/reproducibility.md: add it to addons/vela_setup before continuing." >&2
exit 2
