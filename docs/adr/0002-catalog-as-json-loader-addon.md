# 0002. Demo catalog as JSON + idempotent loader addon

- Status: accepted
- Date: 2026-11-15

## Context
The AI agent (step 4) needs a realistic store: real products, variants, specs, stock
scenarios (out of stock, low, overstock), vendors, reorder rules, promotions, cross-sell.
Hand-entering ~120 products in the UI is not reproducible.

## Decision
`addons/vela_tech_catalog` holds the catalog as JSON (`data/catalog/*.json`, schema in
`SCHEMA.md`) and a Python loader run by `post_init_hook`. Every record gets an xmlid in
the module (`noupdate`), so the load is idempotent and uninstall cleans up. Images are real
photos under free licenses (Wikimedia Commons / Openverse: CC0, PD, CC BY, CC BY-SA),
normalised to 1200×1200 white squares, with per-image attribution in
`data/image_credits/` and `IMAGE_CREDITS.md`. Where no free photo of the newest model
exists, the product is the older real model the photo shows.

## Consequences
The catalog is reviewable in git and rebuildable on any DB. Prices are TND estimates.
Changing an existing product requires an explicit update or reinstall (the loader doesn't
overwrite). Commons rate-limits image search, so run it sequentially.

## Alternatives considered
- Odoo demo data: generic furniture products, no stock scenarios.
- CSV import through the UI: not reproducible, no variants/specs/stock in one pass.
- Stock-photo APIs (Unsplash/Pexels): need keys and show generic, not exact, products.
