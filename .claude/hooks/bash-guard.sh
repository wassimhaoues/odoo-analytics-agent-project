#!/usr/bin/env bash
# =============================================================================
# bash-guard — PreToolUse hook for the Bash tool
#
# Blocks the few commands that would destroy real data or leak secrets here.
# Contract: stdin JSON {"tool_input":{"command":"..."}}; exit 2 = block (stderr
# goes back to the agent); exit 0 = allow.
# Philosophy: block the irreversible only. A guard that fires on ordinary work
# gets disabled, and then it guards nothing.
# Test: .claude/hooks/bash-guard.test.sh
# =============================================================================
set -uo pipefail

payload="$(cat 2>/dev/null || true)"
cmd="$(printf '%s' "$payload" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("tool_input",{}).get("command",""))
except Exception: print("")' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

block() { echo "bash-guard: BLOCKED — $1" >&2; echo "If this is really intended, ask the owner to run it manually." >&2; exit 2; }

REAL_DB='CommercePulse'
OUR_VOLUMES='odoo-db-data|odoo-web-data|odoo-study_odoo-db-data|odoo-study_odoo-web-data'
OTHER_PROJECTS='customer-postgres|shared-mongodb|shared-redis|object-storage'

# 1. Dropping or wiping the real database
echo "$cmd" | grep -qiE "dropdb[^|;&]*\b${REAL_DB}\b" && block "dropping the real database ${REAL_DB}"
echo "$cmd" | grep -qiE "drop[[:space:]]+database[^;]*\b${REAL_DB}\b" && block "DROP DATABASE on ${REAL_DB}"
echo "$cmd" | grep -qiE "(-d|--database)[= ]+${REAL_DB}\b.*(-i|--init)[= ]+base\b" && block "re-initialising base on ${REAL_DB}"

# 2. Destroying Docker volumes that hold all real data
echo "$cmd" | grep -qE "docker[ -]compose[^|;&]*\bdown\b[^|;&]*(-v\b|--volumes)" && block "docker compose down -v deletes the Odoo DB and filestore volumes"
echo "$cmd" | grep -qE "docker volume (rm|prune)" && echo "$cmd" | grep -qE "(${OUR_VOLUMES}|prune)" && block "removing/pruning Docker volumes"
echo "$cmd" | grep -qE "docker system prune[^|;&]*--volumes" && block "docker system prune --volumes"

# 3. Other projects' containers on this machine
echo "$cmd" | grep -qE "docker (stop|rm|kill|restart)[^|;&]*\b(${OTHER_PROJECTS})\b" && block "that container belongs to another project"

# 4. Deleting repo-critical folders
echo "$cmd" | grep -qE "rm[[:space:]]+-[a-zA-Z]*r[a-zA-Z]*f?[[:space:]]+(\./)?(addons|\.git|backups|config|\.claude|docs)/?([[:space:]]|$)" && block "recursive delete of a top-level project folder"

# 5. Git: force push to main, committing secrets
echo "$cmd" | grep -qE "git push[^|;&]*(--force|-f\b|--force-with-lease)[^|;&]*\b(main|master)\b" && block "force-push to main"
echo "$cmd" | grep -qE "git push[^|;&]*\b(main|master)\b[^|;&]*(--force|-f\b)" && block "force-push to main"
echo "$cmd" | grep -qE "git add[^|;&]*(-f|--force)[^|;&]*(\.env\b|odoo\.conf\b|\.dump\b|backups/)" && block "force-adding a git-ignored secret/backup"
echo "$cmd" | grep -qE "git add[^|;&]*(^|[[:space:]])(\.env|config/odoo\.conf)([[:space:]]|$)" && block "adding .env / odoo.conf to git"

exit 0
