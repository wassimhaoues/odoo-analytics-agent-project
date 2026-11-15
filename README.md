# Odoo Analytics Agent Project — Vela Tech

[![CI](https://github.com/wassimhaoues/odoo-analytics-agent-project/actions/workflows/ci.yml/badge.svg)](https://github.com/wassimhaoues/odoo-analytics-agent-project/actions/workflows/ci.yml)

Study project (2 developers): an Odoo 20 eCommerce store for tech products ("Vela Tech"),
a custom analytics addon that tracks visitor behaviour, a big-data pipeline (Kafka, Spark,
Hadoop), and an AI agent addon (voice + text) that reads the analytics, talks to the shop
owner and performs actions.

## Roadmap

1. **Store**: catalog (`vela_tech_catalog`) ✅ · custom theme (`vela_theme`): ✅ all phases (header, footer, homepage + motion, shop, product page, cart, checkout, empty states, dark mode)
2. **Analytics addon** (`vela_analytics`): page views, clicks, sessions, cart events
3. **Big data pipeline** (`pipeline/`): Kafka → Spark → HDFS
4. **AI agent addon** (`vela_ai_agent`): voice/text agent with analytics tools and actions

## Get the identical store (new machine / new teammate)

Requirements: Docker + Docker Compose, git, openssl, curl. Ports: 8069 free on localhost.

```bash
git clone https://github.com/wassimhaoues/odoo-analytics-agent-project.git
cd odoo-analytics-agent-project
./scripts/setup.sh
```

In ~5 minutes you get the same Odoo build (pinned image), the same apps, settings, website,
products, variants, stock and images as everyone else. The site runs at
http://localhost:8069/shop, and the back office login is `admin` / `admin` (change it).
`setup.sh` prints the database-manager master password once. Save it.

## Daily workflow (two developers)

```bash
git checkout main && git pull
./scripts/update.sh                 # apply teammates' changes to your database
git checkout -b feat/<thing>
# ... work ...
./scripts/drift.sh                  # must say "No drift" before you push
git push -u origin feat/<thing>     # open a PR, the other person reviews, then merge
```

**The one rule:** the database is built from git, never the other way round. If you install
an app or change a setting in the Odoo UI, also put it in `addons/vela_setup` (apps →
`__manifest__.py` depends, settings → `models/vela_setup.py`), otherwise your teammate won't
have it. `drift.sh` catches forgotten app installs. Details:
[.claude/rules/reproducibility.md](.claude/rules/reproducibility.md).

**Not shared through git:** orders, visitors, analytics events, passwords, personal data.
To share a data snapshot: `./scripts/backup.sh CommercePulse`, send the folder privately,
`./scripts/restore.sh backups/<dir> <newdb>`.

## Layout

```
docker-compose.yml   Odoo 20 + Postgres 17, images pinned by digest
.env.example         secrets template (setup.sh creates .env)
config/              odoo.conf.example (setup.sh creates odoo.conf)
addons/
  vela_setup/          the store's state: all apps + our addons + shared settings
  vela_theme/          look & feel (Sidi Bou Said palette, Archivo, glass header, motion)
  vela_tech_catalog/   demo catalog (JSON + loader + real CC-licensed images)
pipeline/            Kafka / Spark / Hadoop (step 3)
scripts/             setup · update · drift · backup · restore · screenshot · catalog/
docs/                adr/ (decisions), specs/ (requirements)
.claude/             shared Claude Code config: rules, skills, agents, hooks
```

## CI (GitHub Actions)

Every pull request and push to `main` runs `.github/workflows/ci.yml`:

| Job | Checks |
|---|---|
| Lint & static checks | ruff, XML/JSON/Python syntax, addon manifests, `vela_setup` depends on every addon, shellcheck, guard-hook tests, catalog validation, image credits up to date, workflow lint, compose validity |
| Secret scan | gitleaks over the full git history |
| Build store from scratch | `setup.sh` on a clean runner → `update.sh` (idempotent) → `drift.sh` → smoke test → `page_check.mjs --strict` on 6 pages × 3 widths × light/dark. Screenshots and Odoo log uploaded as artifacts |

Merge only when CI is green. Run the same checks locally with the commands in
`.claude/rules/testing.md`.

## Useful commands

| Task | Command |
|---|---|
| Logs | `docker compose logs -f --tail=100 odoo` |
| Rebuild the throwaway test DB | `docker compose exec -T db dropdb -U odoo --force vela_test && ./scripts/setup.sh vela_test` |
| Compare your DB with a fresh build | `./scripts/drift.sh CommercePulse vela_test` |
| Backup / restore | `./scripts/backup.sh <db>` / `./scripts/restore.sh backups/<dir> [newdb]` |
