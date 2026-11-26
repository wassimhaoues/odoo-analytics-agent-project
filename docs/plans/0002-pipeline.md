# Plan 0002: the big-data pipeline (Kafka → Spark → HDFS)

- Status: draft (decisions agreed 2026-11-26, to approve before phase A)
- Spec: [docs/specs/02-big-data.md](../specs/02-big-data.md) (BD-01…06),
  [03-combined-architecture.md](../specs/03-combined-architecture.md) (snapshot API, fallback, IN-01…04)
- Contracts: [.claude/rules/tracking-contract.md](../../.claude/rules/tracking-contract.md)
  (`vela.events.v1`, Odoo → bridge HTTP contract, metric/alert shape)
- Builds on: [plan 0001](0001-vela-analytics.md) (Odoo outbox, local metrics and alerts)
- Decisions to record: ADR 0011 (pipeline architecture), written in phase A

## 1. Goal and place in the project

Roadmap step 3. A standalone stack in `pipeline/` that receives `vela.events.v1` events (from
Odoo's outbox or from its own generator), keeps them in Kafka, processes them with Spark
Structured Streaming, stores history as Parquet on HDFS and serves 5-minute metrics and alerts
through a read-only API. It must run and be graded **without Odoo** (spec 03 §2), and plug into
Odoo for the combined defence.

```
Odoo outbox ──POST /v1/events──┐                       ┌─► HDFS  /vela/clean, /vela/quarantine (Parquet)
generator ──(--via-bridge)─────┤                       │        /vela/checkpoints/<query>
                               ▼                       │
                        gateway (FastAPI) ──► Kafka vela.events.v1 ──► Spark streaming ─┤
generator ──direct──────────────────────────►          ▲                                └─► analytics-db (Postgres)
                                                       │ replay                               metric, alert, daily_*
                        gateway ◄──── reads read-only views ──────────────────────────────────┘
                          │  ├─ GET /v1/snapshot/*, /v1/health, viewer page GET /     Grafana (optional) ┘
                          │  └─ pusher loop ──POST /vela/analytics/pipeline──► Odoo (source=pipeline)
```

## 2. Decisions (agreed 2026-11-26)

| # | Decision |
|---|---|
| P1 | Built here, phase by phase, one branch + PR to `main` per phase; Wassim reviews. |
| P2 | Official Apache images: `apache/kafka` (KRaft, no ZooKeeper), `apache/spark`, `apache/hadoop`. Versions §3. |
| P3 | Spark jobs in **PySpark**. |
| P4 | Results reach Odoo by **push** (changed 2026-11-26, was pull): a **pusher loop in the gateway** sends new/changed rows of the analytics Postgres to a **`vela_analytics` controller** `POST /vela/analytics/pipeline` (Bearer `VELA_PIPELINE_TOKEN`), which validates and upserts `vela.analytics.metric` / `.alert` with `source=pipeline`. Cursor + backoff like Odoo's outbox: Odoo down never slows the Spark stream. The read-only **snapshot API stays** (viewer, spec 03, checks without Odoo); Odoo no longer calls it. |
| P5 | Invalid events → **quarantine Parquet** on HDFS with the raw JSON and a reason; never counted. |
| P6 | **10-minute watermark** on event time: live windows and `event_id` dedup within it. Later events still reach clean Parquet and are counted by the daily batch job. |
| P7 | **Stateless bridge**: validates and produces (idempotent producer, `acks=all`), answers `accepted` / `rejected`, never `duplicate`. Spark is the single dedup point. |
| P8 | Serving tables in an **own Postgres 17 container** (`analytics-db`), not Odoo's database. |
| P9 | Bridge, snapshot API and Odoo pusher in **one FastAPI service** (`gateway`), a separate token for each direction. |
| P10 | Viewer: a **static page served by the gateway** (`GET /`). **Grafana optional** (compose profile `grafana`), reading the same SQL views as the API through a read-only DB user, provisioning (datasource + dashboards) in git. |
| P11 | Generator: Python CLI producing **directly to Kafka**, `--via-bridge` to use the HTTP path like Odoo. |
| P12 | Stack runs **on demand** (`scripts/pipeline.sh up/down`), memory limit on every container. Odoo stays in `local` mode by default; its outbox queues safely while the pipeline is off. |
| P13 | Alert rules: **own copy** in `pipeline/` + a **parity test** (shared golden fixture, both suites assert the same expected metrics and alerts). |
| P14 | CI: ruff + pytest with a local SparkSession on every PR, plus a **small smoke job** (Kafka + gateway + Spark + analytics-db, local files instead of HDFS, one event end to end). |
| P15 | Retention: Kafka **7 days**; clean + quarantine Parquet and 5-minute serving tables **90 days**; daily aggregates **1 year** (small, no personal data). Cleanup in the daily job. |
| P16 | Daily batch job: `scripts/pipeline.sh batch [date]` on demand + a small **scheduler** container while the stack is up. **Idempotent per date** (overwrites that date's partition/rows); on start the scheduler **catches up missed days**. No Airflow. |
| P17 | Odoo reads **pipeline if fresh** (latest window ≤ 15 min old), else local, and says "pipeline stale" (IN-04). The local cron always keeps running. One helper decides. |
| P18 | Odoo switch: `VELA_DELIVERY_MODE=bridge` turns on **both** directions (events out, results in; the controller answers 404 otherwise). `.env` gains `VELA_PIPELINE_TOKEN`; `pipeline/.env` gains `ODOO_URL` (default `http://odoo:8069`) and the same token; `setup.sh` generates matching tokens in both files. |
| P19 | Four phases (§14). |

## 3. Stack and memory budget

`pipeline/docker-compose.yml`, project name `vela-pipeline`, joins the external network
`odoo-analytics-agent-project_default` so Odoo reaches `http://gateway:8000`. Images pinned by
version and digest (same rule as Odoo); our own images built from `pipeline/<svc>/Dockerfile`.

| Service | Image | Mem limit | Host port (127.0.0.1 only) |
|---|---|---|---|
| `kafka` | `apache/kafka:4.3.2` (KRaft, 1 broker+controller, heap 512 MB) | 1 GB | none |
| `namenode` / `datanode` | `apache/hadoop:3.4.3`, replication 1 | 768 MB each | 9870 (NameNode UI) |
| `spark-master` / `spark-worker` | `apache/spark:4.3.0-java21-python3` (1 worker, 2 cores, 1.5 GB executor) | 512 MB / 2 GB | 8080 (Spark UI) |
| `stream` | our image FROM spark: driver of the streaming job, Kafka connector jars baked in | 1 GB | 4040 |
| `scheduler` | same image: daily batch loop (§8) | 1 GB while running | none |
| `analytics-db` | `postgres:17` (same pin as Odoo), own volume | 256 MB | none |
| `gateway` | our FastAPI image | 128 MB | 8090 |
| `grafana` (profile) | `grafana/grafana:13.0.14` | 256 MB | 3000 |

Total ≈ 6–7 GB with everything up; the machine has ~9.5 GB free with Odoo. Kafka connector
jars (`spark-sql-kafka-0-10_2.13:4.3.0` + deps) and the Postgres JDBC driver are downloaded at
image build with pinned versions and checksums, never at job start.

Kafka: topic `vela.events.v1`, 3 partitions, key = `session` (or `event_id`), header `event_id`,
`retention.ms` 7 days. Created by an init step in `pipeline.sh up`, idempotent.

## 4. Gateway (FastAPI)

| Route | Auth | Purpose |
|---|---|---|
| `POST /v1/events` | `Bearer VELA_BRIDGE_TOKEN` | Bridge contract of tracking-contract.md, ≤ 500 events, body ≤ 1 MB. Validates each envelope with the same rules as Spark (`pipeline/common/schema.py`); valid → Kafka, per-event `accepted` / `rejected` + error. Kafka down → 503 (Odoo retries). |
| `GET /v1/snapshot/metrics` | `Bearer VELA_SNAPSHOT_TOKEN` | `?since=<computed_at>&dataset=&key=&limit=`; ordered by `computed_at`, paged by cursor. For the viewer and external checks; Odoo is fed by the pusher (§4.1). |
| `GET /v1/snapshot/alerts` | read token | same paging; alert rows with evidence. |
| `GET /v1/health` | none | freshness: last window, last `computed_at`, last event `ts`, Kafka consumer lag, quarantine count last hour, `stale` flag. No data. |
| `GET /` | none (localhost) | viewer page (P10): latest windows, open alerts with evidence, freshness, quarantine count. Reads `/v1/snapshot/*` with a read token injected server-side; static HTML + small JS, no build step. |

Tokens compared in constant time; unknown fields allowed only as listed in the contract.
Snapshot rows contain no raw events and no personal data (spec 03 §3).

### 4.1 Pusher to Odoo (background task in the gateway)

Every 30 s, when `ODOO_URL` and `VELA_PIPELINE_TOKEN` are set: read `metric` / `alert` rows with
`computed_at` > cursor (table `push_cursor` in analytics-db), POST them in batches of ≤ 500 to
`{ODOO_URL}/vela/analytics/pipeline` as `{"metrics": [...], "alerts": [...]}`, advance the cursor
only after a 200. Errors (Odoo down, 5xx, timeout) → backoff 30 s, 1, 2, 4 … 10 min, logged and
shown in `/v1/health` (`odoo_push`: last success, lag, last error). 401 → error, no retry until
restart. Rows are keyed, so a resend after a crash is a harmless re-upsert.

## 5. Spark streaming job (`pipeline/spark/stream.py`)

One SparkSession, two queries on the same Kafka source (`startingOffsets` = earliest on first
run, then the checkpoint):

1. **ingest** (append, trigger 30 s): parse JSON with the explicit `vela.events.v1` schema →
   - valid → `hdfs:/vela/clean/date=<event date UTC>/` Parquet (snappy), all valid events
     including late and duplicate ones (history is raw truth; batch dedups);
   - invalid → `hdfs:/vela/quarantine/date=<ingest date>/` with `raw`, `reason`, Kafka
     partition/offset (P5).
2. **windows** (update mode, trigger 30 s): valid events → `withWatermark("ts", "10 minutes")`
   → `dropDuplicatesWithinWatermark(["event_id"])` → 5-minute tumbling windows by the metric
   keys of the contract (counts by event/device, checkout error ratio, add-to-cart per SKU,
   zero-result searches, `dataset` from `is_synthetic`) → `foreachBatch`:
   upsert into `metric` (key, window_start, segment, dataset), then run the alert rules for the
   touched windows against the previous 12 windows read from `metric`, upsert into `alert`
   (P13 rules module). Each batch also writes a `stream_health` row (batch id, input rows,
   processed rate, latest offsets).

Checkpoints: `hdfs:/vela/checkpoints/ingest` and `/windows` (one per query). Upserts are keyed,
so replaying a micro-batch after a crash rewrites the same rows (BD-04, no double counting).

## 6. Serving tables (`analytics-db`, schema in `pipeline/sql/*.sql`, applied by `pipeline.sh up`)

- `metric`, `alert`: same columns and keys as Odoo's `vela.analytics.metric` / `.alert`
  (tracking-contract.md §Metrics and alerts), `source` always `pipeline`.
- `daily_funnel` (date, dataset): distinct sessions with page_view / product_view /
  add_to_cart / checkout_started / order_confirmed, session conversion, cart-to-order rate
  (spec 02 §5: the real session conversion, not event ratios).
- `daily_baseline` (date, metric_key, segment, dataset): daily mean/σ per 5-minute slot.
- `stream_health`, `batch_run` (date, status, rows, started/finished).
- Views `v_metric`, `v_alert`, `v_daily_funnel`, `v_health`: the only objects the API and
  Grafana read. Roles: `spark_writer` (tables), `api_reader` (SELECT on views only).

## 7. Generator (`pipeline/generator/`)

`python -m generator <scenario> --minutes 120 --rate <events/s> --total N --seed S [--via-bridge]`
with scenarios `normal`, `checkout_error_spike`, `demand_spike [--sku]`, `zero_result_search`,
`benchmark` (≥ 100 000 events, spec 02 §7). Same funnel shape and spike rules as Odoo's demo
generator, `is_synthetic=true`, `origin=demo`, SKUs from a small catalog file
(`pipeline/generator/catalog.json`, theme SKUs). `--backfill` writes past timestamps for history.
Runs as a one-off container: `scripts/pipeline.sh gen <args>`.

## 8. Daily batch job (`pipeline/spark/daily.py`) and scheduler

For one UTC date: read clean Parquet `date=D`, dedup on `event_id`, compute `daily_funnel` and
`daily_baseline`, **overwrite** that date's rows (idempotent, P16); then retention cleanup
(P15). `scripts/pipeline.sh batch [date]` runs it once. The `scheduler` container loops: on
start, runs every date since the last successful `batch_run` (catch-up), then waits for
00:15 UTC each day.

## 9. Odoo integration (phase D, in `addons/vela_analytics`)

- Controller `POST /vela/analytics/pipeline` (`auth="none"`, `csrf=False`, JSON): 404 unless
  bridge mode; Bearer `VELA_PIPELINE_TOKEN` compared in constant time; body ≤ 2 MB, ≤ 500 rows
  per list; every row validated (known `metric_key` pattern, types, segment format, dataset,
  window alignment) before an upsert under `sudo()` (trust boundary, commented). Upsert keys
  are the models' unique constraints with `source=pipeline`; alert status (acknowledged/resolved)
  set in Odoo is kept, like local. Response: counts of created/updated/rejected rows. Writes
  nothing else (architecture rule: the pipeline writes only its `vela.analytics.*` aggregates).
- `vela.analytics.metric._snapshot(...)`: the one helper that returns pipeline rows if the
  latest pipeline window is ≤ 15 min old, else local rows, with `source` and `stale` flags
  (P17). Views and the future `vela_ai_agent` use it.
- `.env` / `.env.example` / `setup.sh` / `docker-compose.yml`: `VELA_PIPELINE_TOKEN` (P18).

## 10. Configuration and secrets

`pipeline/.env` (git-ignored, template `pipeline/.env.example`): `VELA_BRIDGE_TOKEN` (Odoo →
gateway), `VELA_PIPELINE_TOKEN` (gateway → Odoo), `VELA_SNAPSHOT_TOKEN` (readers of the GET
API), `ODOO_URL`, analytics-db passwords (`spark_writer`, `api_reader`), Grafana admin password.
`setup.sh` generates them and copies the bridge and pipeline tokens into Odoo's `.env`. No host port
outside 127.0.0.1. Infra rule (`.claude/rules/infra.md`): never `down -v` on the pipeline
either; `pipeline.sh reset` is the explicit, confirmed way to wipe pipeline volumes.

## 11. Files

```
pipeline/
  docker-compose.yml  .env.example  README.md
  common/schema.py            envelope schema + validation (gateway and Spark)
  common/rules.py             alert rules + thresholds (copy of vela_analytics/services/metrics.py)
  gateway/  Dockerfile  app/{main,events,snapshot,viewer,pusher}.py  app/static/index.html
  spark/    Dockerfile  stream.py  daily.py  sinks.py
  generator/ Dockerfile  __main__.py  catalog.json
  sql/      001_tables.sql  002_views_roles.sql
  grafana/  provisioning/{datasources,dashboards}/  dashboards/vela.json
  tests/    test_schema.py test_rules.py test_windows.py test_gateway.py test_daily.py
            fixtures/parity/{events.jsonl,expected.json}
scripts/pipeline.sh            up | down | status | gen | batch | logs | reset
```

## 12. Tests

| Test | Proves |
|---|---|
| Unit (pytest, local SparkSession) | schema validation and quarantine reasons; dedup within watermark; window counts; rules; daily funnel; idempotent overwrite |
| Parity (P13) | `fixtures/parity/events.jsonl` → Spark job and Odoo `test_metrics` both produce `expected.json` |
| Gateway | auth, 500-event limit, per-event results, Kafka down → 503 (fake producer); pusher cursor, backoff, no cursor move on failure (fake Odoo) |
| Odoo controller (`vela_analytics` HttpCase) | bad/missing token 401, local mode 404, invalid rows rejected, upsert idempotent, alert status kept, only metric/alert written |
| Smoke (CI) | one event via `POST /v1/events` → Kafka → Spark → `GET /v1/snapshot/metrics` shows it |
| BD-01 | generator publishes; a second consumer group replays from offset 0 |
| BD-02 | `checkout_error_spike` → alert on the spike windows with counts |
| BD-03 | Parquet listed with `hdfs dfs -ls`, queried by `spark.read.parquet` |
| BD-04 | kill `stream` mid-run, restart: serving counts equal a clean run |
| BD-05 | viewer page and `psql` on views without Odoo |
| BD-06 | report: volume, throughput, lag, two failure tests (Kafka down, Spark killed) |
| IN-01…04 | consented `add_to_cart` in Odoo → Kafka → window count pushed back to Odoo; Kafka down doesn't block checkout; Odoo down → pusher catches up after restart; freshness/stale in Odoo |

## 13. Acceptance

All rows of §12 green; `docs/reports/pipeline-benchmark.md` written (BD-06); `drift.sh` clean;
README, CLAUDE.md roadmap and repo map, infra/testing rules, `.env.example` updated.

## 14. Phases (one branch + PR to `main` each)

| Phase | Content | Proves |
|---|---|---|
| A | Compose stack (Kafka, gateway bridge route, generator), `pipeline.sh`, `common/schema.py`, ADR 0011, CI unit job | BD-01, bridge contract with real Kafka |
| B | Spark image, ingest query, HDFS clean + quarantine Parquet, checkpoints | BD-03 |
| C | windows query, rules + parity test, analytics-db tables/views/roles, snapshot API, viewer page, Grafana profile, CI smoke job | BD-02, BD-05 |
| D | daily job + scheduler + retention, gateway pusher + Odoo controller + `_snapshot` precedence, replay/restart tests, benchmark report | BD-04, BD-06, IN-01…04 |

## 15. Risks and open points

- **RAM**: full stack ≈ 6–7 GB. Mitigation: limits per container; `pipeline.sh up` can start a
  subset (e.g. phase A needs only Kafka + gateway).
- **HDFS in Docker** (single DataNode, replication 1): fine for the course, documented as such.
- **Spark 4.3 + Kafka connector**: jars baked into the image; verify the connector version
  matches Spark exactly in phase B.
- **Clock**: all event time in UTC; windows aligned like Odoo's (`floor_window`).
- **Rule fit**: push through a `vela_analytics` controller matches `.claude/rules/architecture.md`
  ("into its own `vela.analytics.*` aggregate models via a controller"). ADR 0011 (phase A)
  records the choice of controller over JSON-RPC and of a pusher over Spark pushing directly.
- **Inbound route on Odoo**: a token-protected public route; it only exists in bridge mode and
  only writes aggregates (security rule: validate, cap size, `sudo()` after validation).
- **Bridge contract**: Wassim to confirm tracking-contract.md §bridge before phase A merges.
- **Benchmark target** (events/s, lag) set after the first measurement in phase D.
