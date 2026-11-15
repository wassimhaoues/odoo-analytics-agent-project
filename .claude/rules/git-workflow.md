# Git workflow

Remote: `github.com/wassimhaoues/odoo-analytics-agent-project` (private). Default branch `main`.

## Two developers

- `main` is always installable: `./scripts/setup.sh` on a fresh machine must work from it.
- Every change goes through a branch + PR; the other developer reviews (no direct pushes to
  `main`. GitHub Free can't enforce it on private repos, so it's a team agreement).
- After merging or pulling: `./scripts/update.sh`, then `./scripts/drift.sh`.
- The PR body says what the teammate must run after pulling (usually `update.sh`; for an
  image bump: `docker compose pull && docker compose up -d && ./scripts/update.sh`).
- Pull before starting work. Keep branches short-lived to avoid conflicts in shared JSON/XML.

## Branches

- One branch per step or feature: `feat/theme-vela`, `feat/analytics-events`, `fix/<thing>`,
  `chore/<thing>`, `docs/<thing>`.
- Commit or push only when the owner asks. Never force-push `main`.

## Commits

- Conventional Commits: `feat(vela_theme): add bento grid snippet`. Scope = addon or area.
- Subject ≤ 50 chars, imperative. Body only when the *why* isn't obvious.
- One logical change per commit. Data + code for one feature may go together.

## Before committing

1. `git status` / `git diff --stat`. No `.env`, `odoo.conf`, dumps, caches, `graphify-out/`.
2. Secret scan: `git diff --cached | grep -iE "passw|secret|api[_-]?key|token"` must
   show only placeholders.
3. Static checks pass (edit-lint hook output clean).
4. Change verified per testing.md, and say what wasn't verified.

## Pull requests

Title = commit style. Body: what, why, how verified, screenshots for UI, follow-ups.
