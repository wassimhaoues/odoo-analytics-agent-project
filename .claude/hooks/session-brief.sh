#!/usr/bin/env bash
# SessionStart hook: a 5-line brief so every session starts oriented. Never fails.
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
dirty="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
last="$(git log -1 --format='%h %s' 2>/dev/null || echo 'no commits')"
code="$(curl -s -o /dev/null -m 3 -w '%{http_code}' http://127.0.0.1:8069/web/login 2>/dev/null || echo 000)"
[ "$code" = "200" ] && odoo="up" || odoo="DOWN (http $code)"
addons="$(ls -d addons/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"

echo "Vela Tech brief — branch: $branch ($dirty uncommitted) · last: $last"
echo "Odoo: $odoo · real DB: CommercePulse · test DB: vela_test · addons: ${addons:-none}"
echo "Read .claude/CLAUDE.md first; load rules for the files you touch."
exit 0
