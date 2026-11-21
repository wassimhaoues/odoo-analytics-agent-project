# 01. Odoo course: `vela_analytics` + `vela_ai_agent`

> Text version of [pdf/01_Odoo_Modules_Specification.pdf](pdf/01_Odoo_Modules_Specification.pdf)
> (academic specification, 07 Nov 2026), with the repo's names (see [README](README.md#names)).

**CommercePulse for Odoo.** Two custom addons for eCommerce event tracking and an AI business analyst.

**Project objective.** Turn Odoo website interactions and business records into understandable
business alerts, dashboards and human-reviewed action proposals, without requiring the Big Data system.

## 1. Problem and proposed solution

Odoo eCommerce provides transactional management, but merchants still need a unified view of
customer behaviour and a clear explanation when sales journeys go wrong. The solution adds
consent-aware event tracking and an AI-assisted investigation workflow within standard Odoo Community.

## 2. Standalone architecture

```
                 Odoo Website / eCommerce (views, carts, checkout, confirmed orders)
                                         │ Odoo backend
            ┌────────────────────────────┴─────────────────────────────┐
  ADDON 1 | vela_analytics                         metrics ──►  ADDON 2 | vela_ai_agent
  JS events + verified order hooks                              Management dashboards, alerts
  Event validation, consent, dedup                              LLM tools + evidence references
  Durable event outbox / delivery state                         Human-reviewed action proposals
            │                                                              │
  Odoo models: event / outbox / metric snapshots                AI model provider (structured tool calling only)
                     No big-data dependency to install or present
          Optional adapter: local demo analytics OR external big-data analytics API
```

Independent Odoo deployment: the analytics adapter uses seeded/local metrics. An external
big-data source is optional.

**Academic boundary:** exactly two custom installable addons (`vela_analytics`,
`vela_ai_agent`); existing Website, eCommerce, Sales, Inventory and Purchase apps may be reused.
No Odoo Enterprise AI features. Target: the university's installed Community release (we use 20.0).
The store-environment addons (`vela_setup`, `vela_theme`, `vela_tech_catalog`) only build the
demo shop; they are not part of the two graded addons.

## 3. Functional requirements

| ID / module | Required behaviour | Verification |
|---|---|---|
| FR-01 `vela_analytics` | Capture consented page/product/search/cart/checkout interactions through website assets and a validated endpoint. | Events visible in internal log. |
| FR-02 `vela_analytics` | Emit `order_confirmed` only from trusted server-side sales/order changes; never trust browser claims. | Order event maps to a real sale. |
| FR-03 `vela_analytics` | Persist an outbox with event UUID, status, retry count and delivery timestamp. | Failure does not block checkout. |
| FR-04 `vela_ai_agent` | KPI dashboard, detected anomalies, time range, segment and supporting counts. | Demo dataset renders correctly. |
| FR-05 `vela_ai_agent` | Explain alerts using controlled tools and cite underlying Odoo records / metric windows. | Reproducible evidence trace. |
| FR-06 `vela_ai_agent` | Propose an internal follow-up task or draft replenishment request; require human approval. | No automatic confirmation. |
| FR-07 both | Configuration, roles, audit trail and a local analytics fallback. | Both addons run without Kafka. |

## 4. Data model and screens

| Model | Addon | Purpose / key fields |
|---|---|---|
| `vela.analytics.event` | vela_analytics | event_id, occurred_at, event, session, visitor, website_id, product_id, consent, payload |
| `vela.analytics.outbox` | vela_analytics | event_id, state, attempts, last_error, next_retry_at |
| `vela.analytics.metric` | vela_analytics | metric_key, window_start/end, segment, numerator, denominator, source |
| `vela.analytics.alert` | vela_analytics | alert_type, severity, window, evidence, detection_rule, status |
| `vela.ai.analysis` | vela_ai_agent | question, tool trace, finding, evidence references, timestamp |
| `vela.ai.proposal` | vela_ai_agent | suggested action, linked record, reviewer, state, execution outcome |

Views: Website tracking settings, Event Monitor, KPI Overview, Alert Detail, AI Analyst
(chat + evidence panel), Approval Queue. Use Odoo ORM, ACL rules, menus, actions and standard views.

## 5. Agent design and tool boundaries

The LLM interprets precomputed metrics and never fabricates numbers. It can call only typed,
read-only functions such as `get_metric_window`, `list_anomalies`, `get_sale_order`,
`get_product_availability` and `get_purchase_status`. One bounded write tool may prepare a draft
task or replenishment request; Odoo permissions and explicit approval gate execution.

## 6. Non-functional requirements

- **Privacy:** consent gate, pseudonymous session ids, minimised payloads, configurable retention.
- **Security:** public endpoint validation / rate limits; ORM ACL and record rules; model credentials server-side.
- **Reliability:** queue/outbox retries; a Kafka or AI-provider failure can't block an order.
- **Explainability:** every alert carries measured values, comparison window, source and linked Odoo records.
- **Performance:** website tracking is asynchronous; dashboards read stored aggregates, not raw-event scans.

## 7. Acceptance tests and live demo

| Test | Pass condition |
|---|---|
| T1 Install independently | Install both addons in a clean Community database and load demo data. |
| T2 Capture and consent | A consented product/cart event appears; declined/absent consent produces no optional analytics. |
| T3 Trusted sale | A test order generates one verified server-side `order_confirmed` event. |
| T4 Explain a failure | Seed a checkout-error spike. The agent identifies the alert and its underlying counts. |
| T5 Controlled action | A proposed task stays pending until an authorised reviewer approves it. |
| T6 Failure mode | A simulated Kafka/API outage leaves checkout usable and retries the outbox. |

## 8. Delivery plan (four weeks)

W1: Odoo environment, model design, views. W2: frontend tracking, server hooks, outbox.
W3: dashboard, alerts, agent tools, proposals. W4: ACL/tests, demo data, screenshots, documentation.

**Outside the MVP:** real payment processing, automatic refunds, fully autonomous purchasing,
live speech, production-scale deployment. (The repo roadmap's voice input is therefore a
post-MVP extra; text chat comes first.)
