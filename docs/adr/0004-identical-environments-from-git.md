# 0004. Identical developer environments built from git

- Status: accepted
- Date: 2026-11-15

## Context
Two developers must see the same Odoo: same build, apps, settings, website, products and
stock. Git carries code, but installed apps and settings live in each developer's Postgres
database. The `odoo:20.0` tag is rebuilt nightly, so two pulls can differ. The first database
was created through the web form (country Tunisia → `l10n_tn`, TND, fr_FR + en_US).

## Decision
- **Pin images by digest** in `docker-compose.yml` (Odoo build 20.0-20261112, Postgres 17).
  Bumping is a deliberate change with its own commit.
- **`addons/vela_setup`** is the store's state: its manifest `depends` lists every app we use
  plus our addons, and an idempotent `vela.setup.apply()` (run on every install/upgrade)
  sets company name, timezone, languages, website and the demo payment provider.
- **`scripts/setup.sh`** builds a store from nothing: config from templates with random
  secrets, `odoo db init --country TN --language en_US` (same as the web form), install
  `vela_setup`. **`scripts/update.sh`** upgrades all our addons after `git pull`.
  **`scripts/drift.sh`** reports apps installed in a DB but not declared in git, and diffs
  two DBs.
- `.claude/rules/reproducibility.md` (always loaded) plus a `state-drift` hook make Claude
  encode every install/setting in `vela_setup` and keep the scripts and docs in sync.
- Transactional data is not shared through git. Snapshots go via backup/restore, privately.

## Consequences
A teammate gets the exact store with one command, and drift is detectable. UI-only changes
are discouraged and must be mirrored in code. Settings drift (vs. app drift) isn't
detected automatically, so it relies on the rule and review.

## Alternatives considered
- Sharing DB dumps through the repo: large, contains personal data, merge conflicts on every change.
- One shared hosted Odoo: no isolation, one developer's experiment breaks the other's work.
- Documenting manual steps in the README: drifts silently, nobody re-reads it.
