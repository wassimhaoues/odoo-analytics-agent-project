# Architecture

## The four steps and how data flows

```
Visitor ──► Odoo website (vela_theme, website_sale)
              │  data-track-* events (JS beacon)          tracking-contract.md
              ▼
          vela_analytics addon ── stores events in Postgres (vela.analytics.event)
              │  produce to Kafka topic  vela.events.v1     (step 3)
              ▼
          Kafka ──► Spark (structured streaming + batch) ──► HDFS (raw / curated)
                                       │
                                       ▼  aggregates written back to Odoo via JSON-RPC
          vela_ai_agent addon ── tools read aggregates + Odoo models, act (promos, restock, content)
              ▲                                             │
              └──── owner talks to it (text / voice) ───────┘
```

## Where code goes

| Code | Place | Rule |
|---|---|---|
| Odoo model/view/controller | `addons/<addon>/` | One addon per capability. Prefix `vela_` (theme = `vela_theme`, never `theme_*`: ADR 0005) |
| Demo/seed data | `addons/vela_tech_catalog/data/` | JSON + loader, never hand-made in the UI |
| Visual design | `addons/vela_theme/` | SCSS tokens, QWeb, snippets. Not website-builder clicks |
| Pipeline jobs | `pipeline/<kafka|spark|hdfs>/` | Own docker compose file `pipeline/docker-compose.yml`, joins the Odoo network |
| One-off tooling | `scripts/` | Must be re-runnable and documented in its docstring |

## Boundaries

- **Addons talk to each other through the ORM**, never through raw SQL on another addon's tables.
- **The pipeline never writes Odoo tables directly.** It reads Kafka and writes back through
  Odoo JSON-RPC, or into its own `vela.analytics.*` aggregate models via a controller.
- **The AI agent acts only through explicit tools** (Python methods with validated
  arguments), never free SQL or `eval`. Every action is logged and reversible where possible.
- **Event schema is versioned** (`vela.events.v1`). Breaking change → new version, not an edit.

## Dependencies between addons

`vela_theme` → website · `vela_analytics` → website_sale · `vela_ai_agent` → vela_analytics.
`vela_tech_catalog` is data only and must stay uninstallable without breaking the others.
