---
paths:
  - "addons/**"
---

# Odoo 20 addon conventions

## Layout

```
addons/vela_<name>/
  __manifest__.py      version "20.0.x.y.z", license LGPL-3, explicit depends, data in load order
  __init__.py
  models/  __init__.py, one file per model (or per inherited model)
  controllers/         http routes
  views/               <model>_views.xml, menus.xml
  security/            ir.access.csv (+ <name>_security.xml for groups)
  data/                noupdate XML or JSON + loader
  static/src/          js/, scss/, xml/ (OWL templates); static/description/icon.png
  tests/               test_*.py, tagged
```

Manifest `data` order: security → data → views → menus.

## Models

- `_name = "vela.<thing>"`, `_description` always set. Inherit with `_inherit`, never copy.
- Every new model needs an `ir.access.csv` line, or it is invisible and logs warnings.
  **v20 replaced `ir.model.access` (and record rules) with `ir.access`**: header
  `id,name,model_id,group_id/id,operation,domain`; `model_id` is the model name
  (`vela.analytics.event`), `operation` a subset of `crud` in that order (`r`, `rd`, `rud`, `crud`),
  `domain` optional (it replaces record rules).
- Prefer stored computed fields with correct `@api.depends`. Never `search()` inside a loop:
  batch with `read_group` / `_read_group`, `mapped`, `filtered`.
- `sudo()` only at a trust boundary, with a comment saying why (see security.md).
- Business logic in model methods. Controllers stay thin.

## Odoo 20 facts (verified in the image — re-verify if in doubt)

- **Binary/Image fields** reject raw `bytes`: pass a base64 **str** (`b64encode(x).decode()`)
  or an `odoo.tools.binary.BinaryValue`.
- **Product type**: `type="consu"` + `is_storable=True` for stocked goods (no `product` type).
- **Buy route** is not product-selectable. Purchase replenishment comes from the warehouse
  (`buy_to_resupply`). Don't write `route_ids` with the Buy route.
- Variant price extras live on `product.template.attribute.value.price_extra`.
- Spec attributes: `create_variant="no_variant"` + `product.attribute.category` drive the
  product page specs and the comparison page.
- Current website: `self.env.website` (no `get_current_website()` in v20).
- Groups: `res.groups.privilege` + `res.groups` with `privilege_id` (see `vela_analytics/security`).
- Ribbons: `product.ribbon` with `assign` = manual | sale | new | out_of_stock.
- Product page text field is `description_ecommerce` (HTML).
- Stock: create `stock.quant` with `inventory_mode=True` context, then `action_apply_inventory()`.

## Data loading

- Seed data: JSON + idempotent loader with xmlids (`noupdate=True`). See `vela_tech_catalog/loader.py`.
- Records created by hooks get an `ir.model.data` row in our module, or upgrades orphan them.

## Upgrades

Use the `odoo-addon-workflow` skill. A model/field change needs `-u <addon>`, a restart alone
is not enough. Python changes need a restart. Asset (JS/SCSS) changes need an assets rebuild
(`-u` or dev mode `--dev=assets`).
