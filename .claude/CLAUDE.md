# Vela Tech — agent instructions

Study project: an **Odoo 20 eCommerce store ("Vela Tech", tech products)** that becomes a
data platform. **Two developers** each run an identical store built from git
(`scripts/setup.sh`). Read this file first, then **always** read
[rules/reproducibility.md](rules/reproducibility.md), then load only the other rule files your task touches.

## Roadmap (one step at a time, in order)

| # | Step | Lives in | Status |
|---|---|---|---|
| 1 | Store: catalog + custom theme | `addons/vela_tech_catalog`, `addons/vela_theme` | catalog ✅ · theme: phase A ✅ (tokens, fonts, header, footer, logo) · B ✅ (homepage + motion) · C ✅ (shop, cards, filters, product page) · D ✅ (cart, checkout, empty states, cookie bar, dark mode) |
| 2 | Analytics addon: who clicked/viewed what | `addons/vela_analytics` | plan `docs/plans/0001` · A ✅ (capture, consent, server events, outbox rows) · B ✅ (outbox cron → HTTP bridge, backoff, fake bridge) · C ✅ (5-min metrics, alerts, demo generator, settings) |
| 3 | Big-data pipeline: Kafka → Spark → HDFS | `pipeline/` | planned |
| 4 | AI agent addon (voice + text) that reads analytics and acts | `addons/vela_ai_agent` | planned |

Specs from the owner are in `docs/specs/` (academic specs, text + PDF; names per ADR 0008:
`vela_analytics`, `vela_ai_agent`, topic `vela.events.v1`). Decisions go in `docs/adr/` (skill: `adr`).

## Repository map

```
docker-compose.yml   Odoo 20 (odoo:20.0 image) + Postgres 17. Secrets in .env (git-ignored)
config/              odoo.conf (git-ignored; template odoo.conf.example)
addons/              our Odoo addons, mounted at /mnt/extra-addons
  vela_setup/          THE store state: depends on every app + our addons; shared settings
  vela_theme/          look & feel: palette, self-hosted fonts, tokens, header/footer, logo, motion
  vela_tech_catalog/   demo catalog loader: JSON in data/catalog → products, variants, stock…
  vela_analytics/      event tracking (endpoint, tracker.js, server hooks), outbox → Kafka bridge,
                       5-min metrics + alerts, demo generator (ADR 0010, plan docs/plans/0001)
pipeline/            Kafka / Spark / Hadoop (step 3)
.github/workflows/   ci.yml: lint · secret scan · store built from scratch + browser checks
scripts/             setup.sh (bootstrap) · update.sh (after pull) · drift.sh (DB vs git) · ci/
                     backup.sh · restore.sh · screenshot.sh · analytics_demo.sh · catalog/ (image + validation tools)
docs/                adr/, specs/, plans/
.claude/             this config
```

Odoo **source is inside the image**, not in the repo. Read it with
`docker compose exec -T odoo grep -rn … /usr/lib/python3/dist-packages/odoo/addons/<module>`.
Always check the real v20 source before assuming an API — v20 differs from v17/18 docs.

## Environment facts

- Odoo: http://localhost:8069 · edition **Community** · currency **TND** · company **Vela Tech**
- DB **`CommercePulse`** = the real store. DB **`vela_test`** = throwaway, dry-run everything here first.
- Postgres has no host port. Use `docker compose exec -T db psql -U odoo -d <db>`.
- Installed apps: website, website_sale(+stock, loyalty, mass_mailing), stock, purchase,
  sale_management, crm, website_crm, website_livechat, website_blog, website_links, survey, payment_demo.
- Payments: no online payment (ADR 0009). Cash on delivery (home delivery) and pay at pickup only;
  Demo and every other provider are switched off by `vela_setup`. 19% VAT on every product, prices tax included.
- Content pages: `/about-us`, `/privacy`, `/cookie-policy`, `/contactus` (vela_theme `views/pages.xml`),
  `/terms` (vela_setup `data/terms_*.html`), blog posts (vela_setup `data/blog_posts.xml`). Cookie bar on.

## Rules — load what you touch

| File | Load when |
|---|---|
| [rules/reproducibility.md](rules/reproducibility.md) | **Always.** Installing apps, changing settings, new addons, anything stateful |
| [rules/architecture.md](rules/architecture.md) | New addon/service, crossing step boundaries, unsure where code goes |
| [rules/odoo-addon.md](rules/odoo-addon.md) | Any Python/XML/CSV under `addons/` |
| [rules/odoo-frontend.md](rules/odoo-frontend.md) | QWeb templates, SCSS, JS under `addons/*/static` or `addons/vela_theme` |
| [rules/design-system.md](rules/design-system.md) | Anything a visitor sees: layout, type, color, motion |
| [rules/tracking-contract.md](rules/tracking-contract.md) | Adding clickable/visible UI, or analytics event code |
| [rules/security.md](rules/security.md) | Controllers, access rights, sudo(), secrets, public routes |
| [rules/testing.md](rules/testing.md) | Writing tests or verifying a change |
| [rules/infra.md](rules/infra.md) | docker compose, DBs, backups, logs, new services |
| [rules/git-workflow.md](rules/git-workflow.md) | Branching, committing, PRs |

## Skills

| Skill | Use for |
|---|---|
| `odoo-addon-workflow` | Create/upgrade an addon safely: dry-run on `vela_test` → apply to `CommercePulse` → verify |
| `catalog-data` | Add/change products, images, stock in the demo catalog |
| `frontend-design` (vendored, Anthropic) | Art direction: a distinctive, non-template look. Run before any new page |
| `ui-ux-pro-max` (vendored) | Design data: palettes, font pairings, UX guidelines, GSAP presets |
| `motion-design` | Lenis + GSAP ScrollTrigger inside Odoo, reduced-motion, perf budget |
| `ponytail` / `ponytail-review` (vendored) | Minimal-code discipline and review for **code** |
| `adr` | Record an architecture decision |

**Ponytail scope:** "smallest change" applies to *code* (Python, XML, JS logic, scripts).
It never applies to design ambition: visual polish, motion and UX states are requirements,
not extras.

## Agents

| Agent | Use for |
|---|---|
| `odoo-scaffolder` | New addon skeleton in our conventions |
| `odoo-reviewer` | Review addon diffs: ORM perf, ACLs, v20 API misuse, security |
| `ui-critic` | Screenshot pages and critique against design-system.md |

## Non-negotiables

1. **No secrets in git.** `.env`, `config/odoo.conf` stay ignored; templates only.
2. **Dry-run on `vela_test` before `CommercePulse`.** Never experiment on the real DB.
3. **Verify v20 APIs in the image source.** Don't trust memory or v17/18 docs.
4. **Everything reproducible from git.** No app, setting, design or data that lives only in
   the DB. Install/setting → `vela_setup`. `./scripts/drift.sh` must stay clean.
5. **Keep the shared files in sync as part of "done"**: `vela_setup`, `setup.sh`/`update.sh`,
   `README.md`, this file's repo map + roadmap status, `.env.example`, ADRs.
6. **Every interactive element carries a `data-track` attribute** (tracking-contract.md).
7. **Report honestly.** Say what was not checked, and what the teammate must run after pulling.
