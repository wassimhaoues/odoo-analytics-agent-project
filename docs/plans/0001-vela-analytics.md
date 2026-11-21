# Plan 0001: `vela_analytics`, the event tracker

- Status: approved (decisions agreed 2026-11-21). Phase A done (ADR 0010); B and C to do
- Spec: [docs/specs/01-odoo-addons.md](../specs/01-odoo-addons.md) (FR-01…03, FR-07, T1–T4, T6),
  [03-combined-architecture.md](../specs/03-combined-architecture.md) (IN-01…04),
  event format [02-big-data.md §3](../specs/02-big-data.md)
- Contracts: [.claude/rules/tracking-contract.md](../../.claude/rules/tracking-contract.md) (`vela.events.v1`)
- Decisions to record: ADR 0010 (tracker architecture: outbox over HTTP bridge, consent, identity)

## 1. Goal and place in the project

`vela_analytics` turns website behaviour and trusted sales facts into versioned events
(`vela.events.v1`), keeps them durably in Odoo, delivers them to Kafka through an HTTP bridge
(at least once), and computes local 5-minute metrics and alerts so the Odoo project works
**without** the pipeline (FR-07). `vela_ai_agent` (step 4) reads those metrics and alerts,
whether they were computed here or by Spark.

```
Browser (data-track ids + Odoo consent)                Odoo server (trusted)
  events held in memory until "I agree"                  add_to_cart, search, checkout errors,
  sendBeacon batch ──► POST /vela/analytics/events       order_confirmed (sale.order confirm)
                          validate · rate-limit · dedup · consent         │
                          ▼                                               ▼
                  vela.analytics.event ──(same transaction)──► vela.analytics.outbox
                          │                                               │ cron 1 min, backoff
                          │ cron 5 min                                    ▼
                          ▼                                   HTTP bridge (pipeline/, Wassim)
          vela.analytics.metric / .alert                                  ▼
             (source = local | pipeline)                       Kafka topic vela.events.v1
                          ▼
                  vela_ai_agent (step 4)
```

Not in this addon: the polished KPI dashboard, Alert Detail page, AI chat and Approval
Queue (FR-04…06, `vela_ai_agent`), the bridge itself and Spark (`pipeline/`), view
impressions (`data-track-type="view"`, discussed later).

## 2. Decisions (agreed 2026-11-21)

| # | Topic | Decision |
|---|---|---|
| D1 | Kafka link | Odoo POSTs batches to an **HTTP bridge** in `pipeline/`, built by Wassim. Odoo image stays official. We ship a fake bridge for tests. |
| D2 | No consent | No browser or server tracking events. **Only `order_confirmed`** is recorded, with no session or visitor id. |
| D3 | Event scope | The spec's business events **plus every `data-track` click** (`event: "click"`). Views later. |
| D4 | Identity | A **per-visit session id** (random) + a **salted hash of the Odoo visitor token**. The real token never leaves Odoo. |
| D5 | Sending | **Cron every minute**, batches, exponential backoff. Checkout never waits on the network. |
| D6 | Metrics and alerts | Computed **in `vela_analytics`** by cron, same shape as Spark's output. |
| D7 | Demo data | **Manager button + CLI script** generating `is_synthetic` scenarios (normal, checkout-error spike, demand spike, zero-result search). |
| D8 | `checkout_error` | **Server** failures (trusted) + **browser** form-validation errors, as a controlled `error_code`, never typed text. |
| D9 | Before consent | Events are **held in browser memory** (never sent), sent if the visitor accepts on that page, discarded on refusal or page exit. |
| D10 | Synthetic data | Metrics carry a **dataset** (`real` / `demo`). Views default to real; demo shows a badge. |

## 3. Who emits which event

| Event | Emitter | When | Extra fields |
|---|---|---|---|
| `page_view` | browser | every page load | `page`, `ref`, `source`, `utm` |
| `product_view` | browser | product page load (`#product_details[data-vela-sku]`) | `product`, `category` |
| `click` | browser | click on any `[data-track]` element (not `auto.*` fallbacks: logged separately as gaps) | `track`, `product`, `category`, `position` |
| `search` | server | `/shop?search=…` rendered | `search_results_count`, `category` (never the search text) |
| `add_to_cart` | server | `/shop/cart/add` succeeds | `product`, `quantity` |
| `checkout_started` | browser | first `/shop/checkout` or `/shop/address` view in the session | — |
| `checkout_error` | server | address submit rejected, payment transaction → `error`, confirm/payment route exception, out of stock at confirm | `error_code` |
| `checkout_error` | browser | checkout form shows validation errors | `error_code = form_validation`, field name |
| `order_confirmed` | server | `sale.order._action_confirm()` for website orders | `sale_order_id`, `quantity`; session/visitor only with consent |

Server events other than `order_confirmed` follow the same consent rule as the browser
(Odoo's `_is_allowed_cookie('optional')`). The browser never sends `order_confirmed`; the
endpoint rejects it (IN-02).

`error_code` values: `address_invalid`, `delivery_unavailable`, `out_of_stock`,
`payment_error`, `payment_rejected`, `server_error`, `form_validation`.

## 4. Identity and consent

- **Consent source:** Odoo's own cookie `website_cookies_bar` (`{"required": true, "optional": bool}`)
  and the browser events `optionalCookiesAccepted` / `optionalCookiesDenied`
  (`website/static/src/interactions/cookies/cookies_bar.js`). The server re-checks consent on
  every request; a browser claim alone is never trusted.
- **Session:** after consent, the browser sets a session cookie `vela_session` (UUID, no
  expiry date, rotated after 30 minutes of inactivity), registered as an *optional* cookie.
  Being a cookie, the server can attach it to server-side events and to `order_confirmed`.
- **Visitor:** computed **server-side only**: `HMAC-SHA256(salt, website.visitor.access_token)`,
  first 16 hex characters. The salt is random per database, created at install, stored in
  `ir.config_parameter` (never in git). The browser never sends a visitor id.
- **Pre-consent hold (D9):** at most 20 events in memory; sent with the consent click; dropped on
  "Only essentials", on close of the banner without choice, and when the page unloads.
- **Retention:** raw events deleted after 90 days (as promised on `/privacy`), sent outbox rows
  after 7 days. Metrics and alerts are aggregates and stay.

## 5. Data model

All models: `ir.model.access.csv`, groups in §10.

**`vela.analytics.event`** (append-only)

| Field | Type | Notes |
|---|---|---|
| `event_id` | Char, unique index | UUID from the emitter; uuid5 for `order_confirmed` (`order:<name>`), so a re-confirm is a no-op |
| `v` | Integer | 1 |
| `event` | Selection | §3 list |
| `track` | Char | `data-track` id, regex-checked |
| `occurred_at` | Datetime, indexed | browser time, clamped to ±24 h of `received_at` |
| `received_at` | Datetime | server time |
| `session` | Char, indexed | null without consent |
| `visitor` | Char | HMAC hash, null without consent |
| `website_id` | Many2one website | server-set |
| `product_id` / `sku` | Many2one product.product / Char | resolved from SKU |
| `category` | Char | public category slug |
| `position`, `quantity`, `search_results_count` | Integer | bounded |
| `error_code` | Selection | §3 list |
| `page`, `ref` | Char | path only (no query string); referrer host only |
| `device` | Selection | mobile/tablet/desktop, server-derived from User-Agent |
| `source` | Char | sanitised `utm_source` or referrer host |
| `sale_order_id` | Many2one sale.order | `order_confirmed` only |
| `consent` | Boolean | |
| `is_synthetic` | Boolean, indexed | demo data |
| `origin` | Selection | browser / server / demo |
| `payload` | Json | bounded extras: `utm`, `viewport` |

**`vela.analytics.outbox`**: `event_id` (Many2one event, unique), `state`
(pending / sent / failed / dead), `attempts`, `last_error`, `next_retry_at`, `sent_at`.

**`vela.analytics.metric`**: `metric_key`, `window_start`, `window_end`, `segment`
(e.g. `device:mobile`, `product:VT-LAP-001`, `all`), `numerator`, `denominator`, `value`,
`source` (local / pipeline), `dataset` (real / demo), `computed_at`. Unique on
(`metric_key`, `window_start`, `segment`, `source`, `dataset`), upserted idempotently.

**`vela.analytics.alert`**: `alert_type`, `severity`, `window_start`/`window_end`,
`segment`, `measured`, `baseline`, `sample_size`, `detection_rule`, `evidence` (Json: counts,
comparison window, linked record ids), `product_id`, `status` (new / acknowledged / resolved),
`source`, `dataset`. One alert per (type, segment, window, dataset).

## 6. Browser → Odoo endpoint

`POST /vela/analytics/events`, `type="http"`, `auth="public"`, `csrf=False` (beacon that writes
only analytics, as allowed by `rules/security.md`).

- Body: `{"events": [ … ]}`, max **32 KB**, max **50 events**. Sent with
  `navigator.sendBeacon` (on `visibilitychange` → hidden, and every 5 s or 20 events while
  visible), `fetch(..., {keepalive: true})` as fallback.
- Validation: unknown fields rejected; enum checks; `track` matches
  `^[a-z0-9_]+(\.[a-z0-9_]+){1,4}$`; SKU matches the catalog pattern; strings length-capped;
  `order_confirmed` from the browser rejected; consent re-checked from the cookie.
- Server sets `website_id`, `visitor`, `device`, `received_at`, `consent`.
- Dedup: existing `event_id` → silently skipped (at-least-once from the browser too).
- Rate limit: per session and per IP (best effort, per worker), default 120 events/min;
  excess dropped and counted. Known bot user agents are ignored.
- `sudo()` only to write events after validation, with a one-line comment.
- Always answers `204`, never an error page, so tracking can't break the site.

## 7. Server-side hooks

| Hook | Where (v20, verify before coding) |
|---|---|
| `order_confirmed` | override `sale.order._action_confirm()` (website orders only) |
| `add_to_cart` | extend the `/shop/cart/add` controller (cart.py) after success |
| `search` | extend the `/shop` controller when `search` is set |
| `checkout_error` | `/shop/address/submit` invalid response; `payment.transaction` set to `error`; exceptions in `/shop/payment/transaction/<order_id>` and `/shop/payment/validate`; stock check at confirm |

Each hook writes the event + outbox row inside the current transaction. A tracking failure
is logged and swallowed: it can never break a cart, a payment or a confirmation (T6, IN-03).

## 8. Outbox delivery to the bridge

- **Cron every minute**: takes up to 500 `pending`/`failed` rows with `next_retry_at <= now`
  (`FOR UPDATE SKIP LOCKED`, so two workers never send the same row), posts one batch.
- **Backoff**: `next_retry_at = now + min(2^attempts, 60)` minutes; after 20 attempts →
  `dead` (visible, manual Retry button). Network errors and 5xx retry the whole batch; 4xx is
  logged as a contract error.
- **Delivery mode** (setting): `local` (rows marked sent with note "local", no network: the
  standalone Odoo course mode) or `bridge`.
- **Config**: `VELA_BRIDGE_URL`, `VELA_BRIDGE_TOKEN` in `.env` → container → read into
  `ir.config_parameter` by `vela_setup`; placeholders in `.env.example`.

**HTTP contract with the bridge (to confirm with Wassim)**

```
POST {VELA_BRIDGE_URL}/v1/events
Authorization: Bearer {VELA_BRIDGE_TOKEN}
Content-Type: application/json
{"events": [ <vela.events.v1>, … ]}            ≤ 500 events

200 {"results": [{"event_id": "…", "status": "accepted" | "duplicate" | "rejected",
                  "error": "…"}]}
401/400 → whole batch refused (config/contract error)   5xx/timeout → retry later
```

Kafka key = `session`, or `event_id` when there's no session (orders without consent). The
`event_id` also goes in a Kafka header; Spark deduplicates on it within its watermark.
`accepted` and `duplicate` both mark the row `sent`; `rejected` marks it `dead` with the error.

## 9. Local metrics and alerts

- **Cron every 5 minutes** computes closed 5-minute windows (and re-computes the last 3 for
  late events) with `_read_group`, never row-by-row. `source = local`, one `dataset` each.
- **Metrics**: event counts by type (segments: all, device, source); `checkout_error_ratio`
  = checkout_error / checkout_started; `add_to_cart` per product; `search_zero_results` count;
  `orders` count. Session-level conversion is **not** claimed from event ratios (spec 02 §5).
- **Alert rules** (thresholds in settings, each alert stores its numbers as evidence):

| Alert | Rule (defaults) |
|---|---|
| `checkout_error_spike` | ratio ≥ 2 × baseline (mean of the same metric over the previous 12 windows) and ≥ 5 errors and ≥ 20 checkout starts |
| `demand_spike` | a product's add_to_cart count ≥ baseline + 3 σ and ≥ 10 |
| `zero_result_search_spike` | zero-result searches ≥ 3 × baseline and ≥ 10 |

- **Freshness (IN-04)**: each metric has `computed_at`; views flag data older than 15 minutes
  as stale.

## 10. Screens, settings, roles

- Menu **CommercePulse ▸ Tracking**: Event Monitor (list / pivot / graph, filters: event,
  dataset, consent, period), Outbox (state, attempts, last error, Retry), Metrics (graph/pivot),
  Alerts (list + form with evidence), Generate demo traffic (wizard).
- **Settings** (`res.config.settings`, encoded in `vela_setup` defaults): tracking on/off,
  delivery mode, retention days, rate limit, alert thresholds.
- **Groups**: *Analytics User* (read events, metrics, alerts; acknowledge alerts),
  *Analytics Manager* (settings, Retry, demo generator, delete). Public users have no model
  access; only the endpoint writes, after validation.

## 11. Demo generator (D7)

Wizard (managers) and `scripts/analytics_demo.py` (runs through `odoo shell`), same function.
Scenarios: `normal`, `checkout_error_spike`, `demand_spike` (choose a SKU), `zero_result_search`.
Parameters: duration (minutes back from now), volume. Events use real SKUs and paths,
`is_synthetic = true`, `origin = demo`, random sessions; option "also send to pipeline"
(through the outbox, flagged synthetic).

## 12. Files

```
addons/vela_analytics/
  __manifest__.py          depends: website_sale, website_sale_stock
  models/  analytics_event.py  analytics_outbox.py  analytics_metric.py  analytics_alert.py
           sale_order.py  payment_transaction.py  res_config_settings.py
  controllers/  events.py (endpoint)  shop.py (cart/search/checkout hooks)
  services/  validation.py  delivery.py (bridge client)  metrics.py  demo.py
  static/src/js/  tracker.js (Interaction: consent hold, batching, clicks, checkout form errors)
  views/  event_views.xml  outbox_views.xml  metric_views.xml  alert_views.xml
          demo_wizard_views.xml  res_config_settings_views.xml  menus.xml
  security/  ir.model.access.csv  analytics_security.xml
  data/  ir_cron.xml  ir_config_parameter.xml (salt created by hook)
  tests/  test_endpoint.py  test_consent.py  test_order_event.py  test_outbox.py
          test_metrics.py  fake_bridge.py
scripts/analytics_demo.py
docs/adr/0010-tracker-architecture.md
```

Also in the same work: `vela_setup` depends + settings, `.env.example` (bridge keys),
`tracking-contract.md` (visitor = hash, session cookie, origin), README / CLAUDE.md roadmap.

## 13. Tests

| Spec test | Automated test |
|---|---|
| T1 install independently | CI `setup.sh` from scratch + `-i vela_analytics` on a clean DB |
| T2 capture and consent | HttpCase: with consent cookie → events stored; without → nothing; tour: hold then accept → held events arrive |
| T3 trusted sale | confirm a website order → exactly one `order_confirmed`; confirm twice → still one; browser `order_confirmed` rejected (IN-02) |
| T4 explain a failure (tracker part) | demo `checkout_error_spike` → metric ratio jump → one `checkout_error_spike` alert with counts |
| T6 failure mode | fake bridge down → checkout still confirms, outbox rows `failed` with backoff; bridge back → `sent` (IN-03) |
| IN-01 (Odoo part) | consented add_to_cart → outbox row → fake bridge receives it with `event_id` |
| Security | oversized body, 51 events, bad `track`, unknown field, rate limit, bot UA → all dropped, site unaffected |

Plus `page_check.mjs --strict` (no JS errors) and `drift.sh` → No drift.

## 14. Phases (one PR each)

| Phase | Content | Proves |
|---|---|---|
| **A. Capture** | models event + outbox (no sending yet), endpoint, `tracker.js` (consent hold, batching, clicks, page/product views, checkout form errors), server hooks, order event, Event Monitor, groups, retention cron, ADR 0010, contract update | T1, T2, T3, IN-02 |
| **B. Delivery** | outbox cron, bridge client, backoff, local/bridge modes, fake bridge, HTTP contract agreed with Wassim, Outbox view + Retry, `.env` keys | T6, IN-01 (Odoo side), IN-03 |
| **C. Metrics** | metric + alert models, 5-min cron, rules, demo generator (wizard + script), Metrics/Alerts views, freshness | T4 (tracker part), IN-04, FR-07 fallback |

Each phase: dry-run on `vela_test` → tests → apply to `CommercePulse` → `drift.sh` →
`page_check.mjs` → PR with CI green.

## 15. Risks and open points

- **Bridge contract** (§8) must be confirmed with Wassim before phase B.
- **View impressions** (D3) postponed: decide before phase C if the agent needs them.
- **RAM**: 15 GB on this laptop, below the spec's 16 GB for the full stack; the local mode
  keeps the Odoo project demo independent of the pipeline.
- **v20 hooks**: controller and model method names in §7 must be re-verified in the image
  before coding (`rules/odoo-addon.md`).
- **Ad blockers** may block `/…/analytics/…` URLs; acceptable for a study project, noted in
  the report.
