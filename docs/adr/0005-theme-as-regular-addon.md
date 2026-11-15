# 0005. The theme is a regular addon named `vela_theme`

- Status: accepted (refines 0003: the custom-theme decision stands, the module name changes)
- Date: 2026-11-15

## Context
ADR 0003 planned `theme_vela`. In Odoo 20, `website/models/ir_module_module.py` treats any
module whose name starts with `theme_` as a website theme: its views/assets are copied per
website only when chosen in the theme picker (`button_choose_theme` / `_theme_load`). A plain
`-i`/`-u` doesn't apply it to the website. That conflicts with ADR 0004 (identical
environments built by `setup.sh`/`update.sh`).

## Decision
The theme is a normal addon, `vela_theme`, depending on `website_sale` and
`website_mass_mailing`. It registers a `vela` colour palette in
`web._assets_primary_variables`, self-hosts fonts, adds SCSS tokens/styles to
`web.assets_frontend`, and inherits core templates with xpath. Website records it needs
(logo, menus, header options) are set idempotently by `vela_setup`.

## Consequences
Installs and upgrades like any addon, so both developers get the same site. It applies to
every website in the DB (we have one). It doesn't appear in the theme picker, and picking
another Odoo theme there would layer on top of it.

## Alternatives considered
- `theme_vela` + calling `_theme_load` from `vela_setup`: works, but relies on Odoo's
  per-website view copying, which makes upgrades and drift harder to reason about.
