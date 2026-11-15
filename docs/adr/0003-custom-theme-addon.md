# 0003. Custom theme_vela addon instead of a stock theme

- Status: accepted
- Date: 2026-11-15

## Context
The owner wants a distinctive, modern, motion-rich store (8pt grid, type system, semantic
tokens, glass, scroll-driven scenes, reduced-motion support). The analytics addon needs
stable `data-track` hooks on every interactive element. Odoo ships ~30 free themes, none
tech-oriented. Website-builder edits live only in the database.

## Decision
Build `addons/theme_vela`: SCSS design tokens, QWeb template inheritance, custom `s_vela_*`
snippets, Odoo 20 Interactions for behaviour, Lenis + GSAP vendored locally. Process per
`.claude/rules/design-system.md`: frontend-design → ui-ux-pro-max → motion-design → build
→ ui-critic.

## Consequences
Design is versioned and reproducible, and tracking hooks are built in. More upfront work,
and core template xpaths must be checked against each Odoo upgrade. The owner can still
edit content in the website builder.

## Alternatives considered
- Stock theme + builder customisation: fast, but not in git and no tracking contract.
- Headless frontend (Next.js + Odoo API): maximum design freedom, but loses website_sale
  features (cart, checkout, visitor tracking, editor) the later steps rely on.
