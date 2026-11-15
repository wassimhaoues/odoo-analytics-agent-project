---
name: catalog-data
description: Add or change products, variants, specs, stock, prices, images or cross-sell rules in the Vela Tech demo catalog (addons/vela_tech_catalog). Use when the owner asks for new products/categories, different stock scenarios, or replacing product images.
---

# Catalog data

Source of truth: `addons/vela_tech_catalog/data/catalog/*.json` (format in `SCHEMA.md`,
shared definitions in `_meta.json`, cross-sell in `crosssell.json`). Never edit products by
hand in the Odoo UI. Change the JSON and reload.

## Add / change products

1. Read `SCHEMA.md` and `_meta.json`. Use the right SKU prefix `VT-<PREFIX>-NNN`.
2. Images (real, freely licensed, must match the product name):
   ```bash
   python3 scripts/catalog/images.py search --sheet /tmp/<scratch>/sheet.png --cols 8 \
     VT-XXX-001="Exact model name|alt query|ov:openverse query"
   # look at the sheet, then:
   python3 scripts/catalog/images.py pick VT-XXX-001 3 5     # main + gallery
   ```
   Commons rate-limits hard. Run searches sequentially, not six in parallel.
3. Edit the JSON (real specs, TND prices ≈ USD × 3.2–3.4, cost below price).
4. `python3 scripts/catalog/validate.py` → no errors.
5. `python3 scripts/catalog/credits.py` → regenerates `IMAGE_CREDITS.md` (CC BY attribution).
6. Load (use `odoo-addon-workflow` for safety):
   - **Dry-run**: shell on `vela_test` with `Loader(env)` + `env.cr.rollback()`.
   - **Real**: the loader is idempotent and skips existing xmlids, so new products load with
     ```python
     from odoo.addons.vela_tech_catalog.loader import load_catalog; load_catalog(env); env.cr.commit()
     ```
     Changing an *existing* product's data needs an explicit update (the loader doesn't
     overwrite), or uninstall + reinstall the addon on a DB without orders.

## Stock scenarios for the AI agent

Keep per subcategory: ≥1 out of stock, ≥1 low (1–4), ≥1 overstock, ≥1 on sale, reorder
rules on ~half. These are deliberate test cases for step 4. Don't "fix" them.
