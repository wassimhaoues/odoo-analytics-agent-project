# 02. Big Data course: data platform (`pipeline/`)

> Text version of [pdf/02_Big_Data_Specification.pdf](pdf/02_Big_Data_Specification.pdf)
> (academic specification, 07 Nov 2026), with the repo's names (see [README](README.md#names)).

**CommercePulse Data Platform.** Independent event-streaming, distributed storage and analytics pipeline.

**Project objective.** Ingest eCommerce-style events at scale, process them continuously, retain
history and detect measurable anomalies using Kafka, Spark and Hadoop HDFS, without requiring Odoo.

## 1. Problem and proposed solution

Clickstream records arrive rapidly, can be late or duplicated, and are hard to analyse with
spreadsheets or transaction-centric databases. Kafka is the durable event stream, Spark
Structured Streaming does the analytics, HDFS keeps Parquet history. A standalone simulator
supplies meaningful test data.

## 2. Standalone architecture

```
Synthetic event generator (CLI modes: normal / checkout errors / demand spike)
        ▼
Apache Kafka, topic vela.events.v1 (keyed by session or entity; replayable)
        ▼
Spark Structured Streaming (validate / deduplicate / 5-min windows / alerts)
        ├──► Hadoop HDFS: raw/clean Parquet partitioned by date; streaming checkpoints
        └──► Analytics PostgreSQL: windowed KPIs, alerts, baselines; idempotent upserts by metric key
Independent review: SQL queries + simple read-only dashboard
```

Deployment: Docker Compose (`pipeline/docker-compose.yml`) for Kafka (single broker), Spark
(driver/worker), HDFS (NameNode/DataNode), analytics PostgreSQL, producer and a minimal results
viewer. Educational topology, not a highly available cluster.

## 3. Canonical event contract `vela.events.v1`

| Field | Type / rule | Example |
|---|---|---|
| `event_id` | UUID; required, unique across retries | `evt-uuid-1` |
| `v` | integer; required (schema version) | `1` |
| `ts` | UTC ISO 8601 timestamp (occurred at) | `2026-11-07T10:00:00Z` |
| `event` | enum: `page_view`, `product_view`, `search`, `add_to_cart`, `checkout_started`, `checkout_error`, `order_confirmed`, `click` | `add_to_cart` |
| `session` | pseudonymous text; required | `s-e302` |
| `website_id` / `product` | integer id / product SKU (`default_code`); product may be null | `1` / `VT-LAP-001` |
| `device` / `source` | limited enum / sanitised source tag | `mobile` / `instagram` |
| `is_synthetic` | boolean; test events are distinguishable | `true` |

Optional bounded fields: `quantity`, `search_results_count`, country-level `region`, a controlled
`error_code`, and the website fields of the tracking contract (`track`, `visitor`, `page`, `ref`,
`category`, `position`, `viewport`, `utm`). Exclude names, email, payment details and free text.
Reject or quarantine invalid records. Full envelope: `.claude/rules/tracking-contract.md`.

## 4. Streaming transformations and stored outputs

| Stage | Required computation / output |
|---|---|
| Ingest + validate | Consume `vela.events.v1`; parse schema, mark invalid events, deduplicate by `event_id` within a bounded event-time watermark. |
| Real-time windows | 5-minute event counts by device, source, event type and product where relevant, with window start/end. |
| Anomaly detection | Compare current rates/counts with matching reference windows; minimum sample sizes and configurable thresholds. |
| Distributed history | Cleaned events as date-partitioned, compressed Parquet on HDFS. Separate checkpoint directory per stream. |
| Serving layer | Upsert windowed KPI and anomaly tables into analytics PostgreSQL; read-only queries / small dashboard. |
| Historical job | Spark batch job: daily distinct-session funnels and comparable daily baselines from stored history. |

## 5. Metrics and interpretation rules

Operational signals: `checkout_error`, `checkout_started` and `order_confirmed` counts,
product/cart activity and 5-minute deltas. Daily business metrics: unique-session conversion
and cart-to-order completion from a session-level historical job. Don't call raw event-count
ratios a verified session conversion rate.

## 6. Demonstration and anomaly scenarios

| Simulated mode | Expected result |
|---|---|
| Normal traffic | Stable baseline windows, no major alerts. |
| Checkout failure spike | Error-count surge and abnormal checkout-error ratio vs a comparable baseline. |
| Demand spike | Unusual growth in product/cart actions for a chosen product SKU. |
| Search zero-result spike | Many explicit zero-result search events for a chosen term category. |

## 7. Reliability, privacy and constraints

- **Correctness:** event ids plus per-output keys for idempotent writes and duplicate detection.
- **Late data:** event-time processing, explicit watermark, defined policy for records past it.
- **Recovery:** persistent Kafka logs, Spark checkpoints, reproducible replay experiments.
- **Governance:** test-only pseudonymous data, `is_synthetic` flag, retention schedule, input validation.
- **Scale:** ≥ 100,000 events in tests if hardware permits; report throughput, lag and resource usage.

## 8. Acceptance criteria

| ID | Evidence |
|---|---|
| BD-01 | Generator publishes valid versioned events to Kafka; consumers can replay them. |
| BD-02 | Spark aggregates windows and records known injected anomalies with supporting counts. |
| BD-03 | Parquet files exist on HDFS, can be listed and queried by Spark. |
| BD-04 | Consumer restart resumes from checkpoints without double-counting serving metrics. |
| BD-05 | A standalone viewer or SQL query exposes KPI and alert tables without Odoo. |
| BD-06 | A short report states event volume, latency/lag and at least two failure tests. |

## 9. Four-week plan

W1: Docker/Kafka/HDFS/Spark, schema and simulator. W2: validation and HDFS Parquet.
W3: windows, anomaly logic, serving tables. W4: checkpoint/replay tests, benchmarking, independent demo.

**Scope control:** no Hive, Airflow, HBase, ML training platform or production cluster unless
the core pipeline is already reliable.
