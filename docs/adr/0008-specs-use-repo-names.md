# 0008. Specs use the repo's names; one event envelope

- Status: accepted
- Date: 2026-11-21

## Context
The academic specs (docs/specs, 07 Nov 2026) named the addons `commercepulse_tracker` and
`commercepulse_intelligence`, the models `commercepulse.*`, the Kafka topic
`commercepulse.events.v1`, and defined a canonical event (`schema_version`, `occurred_at`,
`event_type`, `session_id`, integer `product_id`…). The repo had already planned
`vela_analytics`, `vela_ai_agent`, `vela.analytics.*` and the envelope `vela.events.v1`
(SKU as product id) in tracking-contract.md. Two naming schemes for one system would leak
into code, topics and the defence.

## Decision
The repo's names win, and the specs were updated to match (PDFs in docs/specs/pdf, text
versions next to them, mapping table in docs/specs/README.md):
- addons `vela_analytics` (tracker) and `vela_ai_agent` (AI analyst);
- models `vela.analytics.event|outbox|metric|alert`, `vela.ai.analysis|proposal`;
- Kafka topic `vela.events.v1`;
- one event envelope: the tracking contract's fields plus the spec's required ones
  (`event_id`, `website_id`, `device`, `source`, `is_synthetic`) and the spec's business
  event enum in `event` (plus `click` for other tracked controls). Products are SKUs.
"CommercePulse" stays the project and database name.

## Consequences
Nothing consumes events yet, so this is free now; after the pipeline exists, any change needs
a new event version. The graded "exactly two custom addons" are `vela_analytics` and
`vela_ai_agent`; `vela_setup`, `vela_theme`, `vela_tech_catalog` are the demo-store
environment (confirm with the teacher).

## Alternatives considered
- Rename the repo to the spec's names: more churn, and the theme already emits `vela.*` ids.
- Keep both and map in a bridge: two vocabularies to maintain and explain.
