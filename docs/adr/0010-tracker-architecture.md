# 0010. Tracker architecture: consent, identity, outbox over an HTTP bridge

- Status: accepted
- Date: 2026-11-21
- Plan: [docs/plans/0001-vela-analytics.md](../plans/0001-vela-analytics.md)

## Context
`vela_analytics` must capture website behaviour and trusted sales facts (spec FR-01…03, FR-07,
T1–T3, T6), respect the cookie banner, keep personal data out of events, and feed Kafka
without making checkout depend on Kafka. The official Odoo image has no Kafka client. The
tracking contract said `visitor` = Odoo's `website.visitor` token, a persistent identifier.

## Decision
- **Delivery:** transactional outbox in Odoo (`vela.analytics.outbox`, one row per event, same
  transaction). A cron (phase B) POSTs batches to a small **HTTP bridge** in `pipeline/` that
  produces to Kafka `vela.events.v1`. Odoo keeps the official image. At-least-once: consumers
  deduplicate on `event_id`.
- **Consent:** Odoo's cookie bar is the only source (`website_cookies_bar.optional`), re-checked
  by the server on every request. Without consent: no browser or server tracking events;
  `order_confirmed` is still recorded (a business fact) but with no session or visitor id.
  Events raised before the visitor answers are held in browser memory and sent only if they
  accept; refusal or leaving the page drops them.
- **Identity:** `session` = random UUID in the optional cookie `vela_session` (30 min sliding).
  `visitor` = first 16 hex of HMAC-SHA256(per-database random salt, Odoo visitor token),
  computed server-side; the real token never leaves Odoo. The order keeps the consented
  session so `order_confirmed` links to the visit even when confirmed outside the request.
- **Trust:** the browser may send only `page_view`, `product_view`, `click`, `checkout_started`
  and `checkout_error` (`form_validation`). `search`, `add_to_cart`, server `checkout_error`
  codes and `order_confirmed` come from Odoo itself. Search text is never stored, only the
  result count. Pages are stored without query strings, referrers as host only.
- **Contract additions (backward compatible):** `origin` (browser/server/demo); optional
  `variant` (exact variant code when `product` is the template-level SKU); `error_code` values
  `address_invalid`, `delivery_unavailable`, `out_of_stock`, `payment_error`,
  `payment_rejected`, `server_error`, `form_validation`.

## Consequences
Checkout never waits on the network and works with Kafka down (T6). Analytics lose the first
page of visits that never answer the banner, and all behaviour of visitors who refuse.
Returning visitors are linkable only while the Odoo visitor token stays the same (per browser
session for anonymous visitors, per partner for logged-in ones). One more service (the bridge)
to run in the pipeline stack.

## Alternatives considered
- Kafka client inside Odoo (custom image with confluent-kafka): fewer services, but a custom
  image to build, pin and keep in sync for both developers.
- Debezium/relay reading the outbox table: breaks "the pipeline never touches Odoo tables".
- Session-only identity: most private, but no returning-visitor analysis. Raw visitor token:
  simplest, but exports a persistent Odoo identifier.
- Counting anonymous events without consent: more complete metrics, harder to defend under
  the spec's consent rule.
