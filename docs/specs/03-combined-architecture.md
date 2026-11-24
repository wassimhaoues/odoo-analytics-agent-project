# 03. Combined architecture: Odoo ↔ Big Data

> Text version of [pdf/03_Combined_Architecture_Specification.pdf](pdf/03_Combined_Architecture_Specification.pdf)
> (academic specification, 07 Nov 2026), with the repo's names (see [README](README.md#names)).

**One ecosystem. Two projects.** Preserve two separately assessable university projects, then
show how live Odoo behaviour becomes streamed evidence that an AI analyst can investigate and act upon.

## 1. Combined reference architecture

```
Odoo eCommerce website (visitor interactions, server-confirmed sales events)
   ▼
ADDON 1 | vela_analytics ──► Kafka (vela.events.v1) ──► Spark (streaming KPIs + anomaly rules)
  consent-aware tracking                                   ├──► HDFS (Parquet history, checkpoints)
  outbox + delivery retry                                  └──► Analytics DB / API (metrics + alerts, read-only)
  canonical event v1                                                    │ API snapshot pull
ADDON 2 | vela_ai_agent ◄────────────────────────────────────────────────┘
  dashboard + alerts, evidence-based AI investigation,
  Odoo inventory / sales tools, reviewable action proposals
```

## 2. Independence is a design requirement

| Presentation | Runs using | Teacher can evaluate |
|---|---|---|
| Odoo course alone | Odoo website + the two addons + seeded/local KPIs + LLM/mock AI | Native models/views, event capture, explanations, approvals |
| Big Data course alone | Synthetic generator + Kafka/Spark/HDFS + analytical viewer | Streaming, historical storage, anomalies, recovery |
| Combined defence | Live Odoo events + event bridge + analytics API + Odoo AI agent | Evidence flowing end to end and influencing decisions |

## 3. Interfaces and responsibility boundaries

| Contract | Producer → consumer | Guarantee |
|---|---|---|
| Event stream `vela.events.v1` | `vela_analytics` outbox → Kafka | Canonical JSON; stable `event_id`; server-only `order_confirmed`; at-least-once with deduplication |
| Analytics snapshot API | Big Data read-only service → `vela_ai_agent` | Authenticated GET for metric windows, anomalies, source and freshness; no raw personal data |
| Action execution | `vela_ai_agent` → Odoo services | LLM suggests a draft; authorisation, business rules and human approval decide execution |
| Fallback mode | `vela.analytics.metric` (local store) → `vela_ai_agent` | Same snapshot shape when the pipeline is down or for separate grading |

## 4. End-to-end sequence: checkout anomaly

1. Visitors consent to optional tracking; Odoo sends website events via its durable outbox. A failed send stays queued.
2. Kafka receives keyed JSON events; Spark validates and aggregates time windows.
3. Spark stores Parquet on HDFS and writes measured anomalies into analytics PostgreSQL.
4. The Odoo analyst retrieves a read-only snapshot, adds sales/order context and reports the evidence.
5. A manager reviews and approves a suggested follow-up task, if appropriate.

## 5. Failure modes and integration tests

| Test | Expected behaviour |
|---|---|
| IN-01 Correctness | One consented `add_to_cart` appears in Kafka and in the right windowed count. |
| IN-02 Source of truth | The browser can't fabricate `order_confirmed`; the Odoo backend emits it. |
| IN-03 Availability | A Kafka outage doesn't interrupt checkout; retries are visible. |
| IN-04 Freshness | Dashboard shows the metric timestamp and marks stale values when the pipeline stops. |
| IN-05 Agent grounding | Explanation includes measured window, comparison and Odoo record links. |
| IN-06 Approval | The AI can't confirm a purchase or alter inventory without authorised human review. |

## 6. Shared delivery plan

| Week | Odoo | Big Data | Connection checkpoint |
|---|---|---|---|
| 1 | Install Odoo; models/views | Docker stack, Kafka, simulator | Freeze event JSON v1 and API fields |
| 2 | Capture events; outbox; local demo data | Spark validation + HDFS storage | Publish real Odoo test events to Kafka |
| 3 | AI dashboard, evidence tools, draft actions | KPIs, anomaly detection, serving API | Show real Spark alerts in Odoo |
| 4 | Security/testing, presentation | Replay/testing, presentation | Run the integrated scenario, record evidence |

## 7. Defence script (6–8 minutes)

| Minute | Show |
|---|---|
| 0–2 | The Odoo website: browse a product, add it to cart; show the tracker event + outbox. |
| 2–4 | Kafka topic, Spark job, HDFS Parquet, KPI/alert table. Inject a synthetic checkout-error spike. |
| 4–6 | Odoo AI analyst: "Why are checkouts failing?" Inspect the evidence and proposed action. |
| 6–8 | Approve a draft follow-up. Switch off Kafka: checkout keeps working with queued events. |

## 8. Evaluated separately

Odoo rubric: two genuine Community addons; models and menus; ORM/ACL; usable UI; agent tools,
traceability, approvals. Big Data rubric: streaming; Spark transformations and windowing; HDFS
files; checkpointing; analytical queries; measurable anomaly tests. Combined rubric: common
contracts, integration resilience, factual explanations, a complete business story.

## 9. Risks, assumptions, exclusions

- Odoo release: the university's Community version; adjust hook/asset APIs (we run 20.0).
- Hardware: ≥ 16 GB RAM preferred for the multi-container demo; reduce services if needed.
- Data quality: transparent synthetic scenarios; keep `is_synthetic` so test events never mix with business reporting.
- Analytics honesty: patterns are evidence, not proof of causality. Report watermark, freshness and sample size.
- Out of scope: payment gateway internals, automatic refunds/replenishment, production HA, enterprise-only AI.
