---
paths:
  - "addons/vela_theme/**"
  - "addons/vela_analytics/**"
  - "addons/*/views/*templates*.xml"
  - "addons/*/static/src/js/**"
---

# Tracking contract (theme ↔ analytics ↔ pipeline)

The theme emits, `vela_analytics` collects, the pipeline and AI agent consume.
This contract is what keeps those three in sync. Change it only through an ADR.

## Markup

Every element a visitor can click, or a section whose visibility matters, carries:

| Attribute | Required | Example | Meaning |
|---|---|---|---|
| `data-track` | yes | `hero.cta.shop_now` | Stable id `<area>.<component>.<action>`, snake_case, never reused |
| `data-track-type` | yes | `click` / `view` / `submit` | Interaction kind |
| `data-track-product` | on product UI | `VT-LAP-001` | Product SKU (`default_code`), never the DB id |
| `data-track-category` | on category UI | `laptops` | Public category slug |
| `data-track-position` | in lists | `3` | 1-based index in a grid/carousel |

Areas: `header`, `megamenu`, `hero`, `rail`, `bento`, `deals`, `shop`, `filters`, `product`,
`recommend` (alternative/accessory product snippets), `carousel`, `cart`, `checkout`, `search`,
`footer`, `promo`, `chat`, `consent` (cookie bar), `empty` / `<area>.empty.*` (empty states),
`account` (login, signup, password reset), `page` (content pages: about, privacy, cookies, blog;
`page.<page>.<action>`), `auto` (fallback only, see below). Added by ADR 0007, `page` by ADR 0009.

## Where ids are set

- Our templates: directly in QWeb (`views/*.xml`).
- Odoo-core UI we don't template: `static/src/js/tracking_annotations.js` (header/footer)
  and `static/src/js/shop_tracking.js` (shop, filters, product page). The `RULES` list there
  also re-applies on DOM changes, for content Odoo injects later (dynamic snippets, dialogs).
- Product SKU: `data-vela-sku` on shop tiles and `#product_details` (views/shop.xml). The
  scripts copy it to `data-track-product`.
- **Fallback:** any interactive element no rule covers gets `auto.<area>` plus
  `data-track-auto="1"`. Analytics still sees the click, and `scripts/page_check.mjs` lists it
  under `autoTracked`. A non-empty `autoTracked` is a gap: add a named rule.

## Event envelope `vela.events.v1`

```json
{ "v": 1, "event_id": "<uuid, stable across retries>", "event": "click",
  "track": "hero.cta.shop_now", "ts": "2026-11-15T10:00:00.000Z",
  "visitor": "<website.visitor access_token>", "session": "<uuid per tab session>",
  "website_id": 1, "page": "/shop/category/laptops", "ref": "<document.referrer>",
  "product": "VT-LAP-001", "category": "laptops", "position": 3,
  "device": "desktop", "source": "instagram", "is_synthetic": false,
  "viewport": "1440x900", "utm": {"source": "", "medium": "", "campaign": ""} }
```

This is also the spec's canonical Kafka event (docs/specs/02-big-data.md §3, ADR 0008).
Required: `v`, `event_id`, `event`, `ts`, `session`, `website_id`, `is_synthetic`.
`event` is one of `page_view`, `product_view`, `search`, `add_to_cart`, `checkout_started`,
`checkout_error`, `order_confirmed` (server only, never from the browser), or `click` for any
other tracked control (its `track` id says which). Optional bounded fields: `quantity`,
`search_results_count`, `region` (country level), `error_code`.

## Rules

- Ids describe **intent, not layout**: `product.add_to_cart`, not `button_3`.
- No personal data in events (no names, emails, addresses, typed text).
  The visitor id is Odoo's `website.visitor` token.
- Respect Do Not Track / consent once the cookie banner exists: no beacon before consent.
- Built-in Odoo tracking (`website.track`, visitor page views) stays on. We add to it.
