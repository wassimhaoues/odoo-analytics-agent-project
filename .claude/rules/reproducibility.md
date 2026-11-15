# Reproducibility: two developers, one identical store

Two people develop this project. Each runs their own Odoo, built from git with
`./scripts/setup.sh`. **Anything that exists only in your database does not exist for
your teammate.** This rule applies to every task, always.

## The contract

| If you… | You must also… |
|---|---|
| install an Odoo app (`-i x`, Apps menu) | add it to `addons/vela_setup/__manifest__.py` `depends` |
| change a setting in the UI (company, website, payments, languages, config) | encode it in `addons/vela_setup/models/vela_setup.py` (idempotent) |
| create a new addon in `addons/` | add it to `vela_setup` depends, the repo map in `.claude/CLAUDE.md`, and the README |
| add/change products, stock, prices, images | change `vela_tech_catalog` JSON (skill `catalog-data`), never the UI |
| edit the website design | do it in `vela_theme` code. Builder clicks are content-only and local |
| add a service/container | add it to a compose file + `.env.example` + `rules/infra.md` |
| add a secret/config key | add a placeholder to `.env.example` / `config/odoo.conf.example` |
| bump the Odoo/Postgres image | update the pinned digest, write an ADR, tell the teammate to run `update.sh` |
| make a decision someone will question | write an ADR (skill `adr`) |

## Keep these files in sync (part of "done")

- `addons/vela_setup/` is the store's state.
- `scripts/setup.sh`, `scripts/update.sh`, `scripts/drift.sh`: update them when the
  bootstrap or upgrade flow changes.
- `README.md` (human onboarding) and `.claude/CLAUDE.md` (agent index, roadmap status).
- `.env.example`, `config/odoo.conf.example`.

## Verify before calling it done

1. `./scripts/drift.sh` prints "No drift" for `CommercePulse`.
2. For changes to `vela_setup` or the bootstrap: rebuild `vela_test` from scratch
   (`docker compose exec -T db dropdb -U odoo --force vela_test` + `./scripts/setup.sh vela_test`) and compare:
   `./scripts/drift.sh CommercePulse vela_test`.
3. Tell the owner what the teammate must run after pulling (usually `./scripts/update.sh`).

## Not shared through git (by design)

Transactional data (orders, visitors, analytics events, pipeline output), admin passwords,
personal contact data. Share data snapshots with `scripts/backup.sh` / `restore.sh` through
a private channel, never committed.
