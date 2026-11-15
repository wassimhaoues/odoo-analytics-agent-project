# 0007. Tracking areas added before the pipeline depends on them

- Status: accepted
- Date: 2026-11-15

## Context
Building phases C and D surfaced interactions the original area list didn't cover: cookie
consent, empty states, product recommendations, carousels, the add-to-cart options dialog,
and an automatic fallback for controls no rule names. The final design review flagged
`consent.*` as off-contract. Step 3 (Kafka/Spark) will key on these ids, so they have to be
fixed now.

## Decision
`vela.events.v1` areas now also include:
- `consent`: `consent.accept_all`, `consent.essential_only`, `consent.close`, `consent.policy_open`
- `recommend`: alternative/accessory product snippets
- `carousel`: gallery navigation
- `<area>.empty.*`: empty-state actions (`cart.empty.deals`, `wishlist.empty.shop`, `search.empty.category`…)
- `product.configurator.*`: the add-to-cart options dialog, carrying the SKU that opened it
- `checkout.*` / `cart.*`: steps, summary, coupon, quick reorder
- `account.*`: `account.login.submit`, `account.signup.submit`, `account.signup.open`, password reset/visibility
- `auto.<container>` + `data-track-auto="1"`: fallback only. It's a gap to name, never a stable id.

## Consequences
Ids are stable from the first push. Renaming any of them later needs a new ADR and an event
version bump, as the contract says.
