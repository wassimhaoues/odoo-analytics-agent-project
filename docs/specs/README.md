# Specs

Owner specification documents. The PDFs in [pdf/](pdf/) are the academic specifications
(07 Nov 2026) with names aligned to this repo; the Markdown files are their text versions.

| Spec | Covers | Lives in |
|---|---|---|
| [01-odoo-addons.md](01-odoo-addons.md) | Odoo course: tracking addon + AI analyst addon (FR-01…07, T1…T6) | `addons/vela_analytics`, `addons/vela_ai_agent` |
| [02-big-data.md](02-big-data.md) | Big Data course: Kafka → Spark → HDFS + analytics DB (BD-01…06) | `pipeline/` |
| [03-combined-architecture.md](03-combined-architecture.md) | Contracts between both, integration tests (IN-01…06), defence script | both |

## Names

The specs originally used CommercePulse names; they now use the repo's (ADR 0008).
"CommercePulse" stays the project and database name.

| Original spec name | Repo name |
|---|---|
| addon `commercepulse_tracker` | `vela_analytics` |
| addon `commercepulse_intelligence` | `vela_ai_agent` |
| `commercepulse.event` / `.outbox` / `.metric` / `.alert` | `vela.analytics.event` / `.outbox` / `.metric` / `.alert` |
| `commercepulse.analysis` / `.proposal` | `vela.ai.analysis` / `vela.ai.proposal` |
| Kafka topic `commercepulse.events.v1` | `vela.events.v1` |
| event fields `schema_version`, `occurred_at`, `event_type`, `session_id`, `device_type` | `v`, `ts`, `event`, `session`, `device` |
| `product_id` (integer) in events | `product` (SKU, e.g. `VT-LAP-001`) |
