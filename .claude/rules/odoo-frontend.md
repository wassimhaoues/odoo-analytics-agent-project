---
paths:
  - "addons/vela_theme/**"
  - "addons/*/static/**"
  - "addons/*/views/*templates*.xml"
---

# Odoo website frontend

The website is **server-rendered QWeb + SCSS + Odoo JS**, not React. Work with Odoo, not against it.

## Theme addon (`vela_theme`)

- **Deliberately not a `theme_*` module** (ADR 0005): Odoo applies `theme_*` modules only
  through the theme picker (per website, copied views). `vela_theme` is a normal addon so
  `setup.sh`/`update.sh` install it identically for everyone. Never rename it `theme_*`.
- Palette: registered in `static/src/scss/primary_variables.scss` (`$o-color-palettes` key
  `vela` + `$o-website-values-palettes`) in `web._assets_primary_variables`, so builder colour
  pickers match. Semantic tokens: CSS custom properties in `tokens.scss` (`web.assets_frontend`).
- Fonts are self-hosted in `static/fonts` (`fonts.scss`), not Odoo's Google font configs.
- Website state the theme needs (logo, menus, header options on/off) is set in
  `vela_setup` (`models/vela_setup.py`), not in the theme and not via builder clicks.
- Header/footer: style Odoo's own markup with SCSS. Replace only inner content (footer
  section), keep `data-name`, `oe_structure`, ids, so the builder keeps working.
- Templates: inherit with `xpath` (`inherit_id`, `priority`), never replace whole core
  templates. Core layouts (`website.layout`, `website_sale.products`, `website_sale.product`)
  change between versions: check the v20 source before writing an xpath.
- Custom building blocks = snippets (`s_vela_*`) registered for the website builder, so the
  owner can still edit content visually without breaking structure.
- Keep the website builder working: editable text stays in normal elements (no text
  baked into JS), and `data-oe-*` attributes are untouched.

## JavaScript

- Use the Odoo 20 frontend **Interactions** API (`@web/public/interaction`) for
  behaviour bound to DOM. Check the v20 source for the exact registry/class, not memory.
- Third-party libs (GSAP, Lenis) are **vendored** into `static/lib/<lib>-<version>/` with
  their license. Never load from a CDN (offline, privacy, reproducibility).
- No global listeners without cleanup. Interactions must destroy what they create
  (the website builder re-renders the DOM).
- Respect the editor: disable motion/scroll hijacking when `document.body` is in edit mode.

## Odoo 20 gotchas we hit

- xpath `hasclass('x')` only matches a literal `class` attribute. Many core templates use
  `t-attf-class`, so target by tag/id instead (e.g. `//article`, `//div[@id='product_details']`).
- Interactions: `this.addListener()` only works in `start()`, not `setup()` (JS error on every page).
- Passing values to a `t-call`: use attributes on the t-call (`<t t-call="x" foo="'bar'" title.f="Text"/>`),
  like Odoo's own templates. `t-set` inside the t-call body did NOT reach the callee here.
- Namespaced SVG templates (`xmlns=".../svg"`): xpath with `//*[local-name()='svg']`.
- Shop look is website fields (`shop_ppr`, `shop_gap`, `shop_opt_products_design_classes`,
  `product_page_image_*`) set in `vela_setup`, not templates. Shop filters show attributes
  with `visibility = 'visible'` only (also set in `vela_setup`); the product spec table ignores it.
- `./scripts/update.sh` exits 1 and prints the traceback if the registry fails to load. Never
  trust filtered upgrade output.

## SCSS gotchas (Odoo's libsass)

- CSS `min()`/`max()` with mixed units fail ("Incompatible units") because libsass treats
  them as Sass math. Write `unquote("min(440px, 80%)")`. `clamp()` and `calc()` are fine.
- Odoo caches bundles per process: after editing SCSS/JS run `docker compose restart odoo`
  (or `update.sh`), otherwise the old (or broken) bundle keeps being served.
- One SCSS error drops the WHOLE `web.assets_frontend` CSS (site unstyled). After any SCSS
  change: `docker compose logs --since 5m odoo | grep -A3 "error occurred while compiling"`.
- Verify pages with `node scripts/page_check.mjs <out> /path` (real mobile emulation, JS
  errors, horizontal overflow, untracked controls), not just `scripts/screenshot.sh`.

## Assets and performance

- Images: WebP/AVIF where possible, explicit width/height, `loading="lazy"` below the fold.
- Budget: LCP < 2.5 s, CLS < 0.1, no long main-thread tasks from animation on load.
- Fonts: self-hosted in `static/fonts`, `font-display: swap`, preload only the hero face.
