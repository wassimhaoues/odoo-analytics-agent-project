---
paths:
  - "addons/vela_theme/**"
  - "addons/*/static/src/scss/**"
  - "addons/*/views/*templates*.xml"
---

# Design system — the owner's brief, as rules

Goal: the site must look crafted by a senior UI/UX designer, never a template.
Process: `frontend-design` (art direction) → `ui-ux-pro-max` (data) → `motion-design`
(motion) → build → `ui-critic` (review). The owner's brief below **wins** over any skill
default (e.g. `frontend-design` calls monospace data labels a tell; the brief asks for them).

## 1. Layout & spatial rhythm

- **8pt grid**: every padding, margin, gap and size is a multiple of 8px (4px allowed only
  for hairline optical tweaks inside components). Use tokens `--space-1…--space-16` (= n×8px).
- Generous negative space, one clear focal point per section, obvious hierarchy.
- Feature showcases use a **Bento grid** (CSS Grid, mixed spans). Icons and badges are
  **optically** aligned (nudge by eye, not just box-centered).

## 2. Typography

- Three roles: a distinctive **display** face, a clean **sans** body face, a **monospace**
  for tags, specs, SKUs and data. Self-hosted, chosen deliberately (not Inter/Roboto/Arial by reflex).
- Modular type scale (ratio ~1.25 body / ~1.333 display), tokens `--fs-xs…--fs-5xl`.
- Large headlines: negative tracking (≈ -0.02 to -0.04em), tight leading (1.0–1.15).
  Body: leading 1.5–1.6, line length < 75ch.
- `font-variant-numeric: tabular-nums` on **all** prices, metrics, stock counts, ratings.

## 3. Surface, depth & color

- **60-30-10**: 60% surface, 30% secondary surface/text, 10% accent.
- Components use **semantic tokens only**, never raw hex:
  `--surface-primary --surface-secondary --surface-raised --text-primary --text-muted
  --border-subtle --accent-primary --accent-contrast --state-success|warning|danger`.
- Light and dark themes both defined from the same semantic tokens.
- Hairline borders: `1px solid` at low opacity (`--border-subtle`).
- Elevation: multi-layer shadows (`--shadow-1…--shadow-4`, each 2–3 stacked layers).
- Glass (`backdrop-filter: blur()` + translucent surface) for the floating header,
  overlays and mega-menu only, with a solid fallback when unsupported.

## 4. Interactive states & feedback

- Every interactive element defines: default, **hover**, **focus-visible** (visible ring,
  never removed), **active/pressed**, **disabled**, and **loading** where async.
- Micro-interactions that show what changed: add-to-cart confirmation, icon morphs,
  button press feedback. Transition 120–240ms, ease-out for enter, faster exit.
- **Skeleton screens** for async content (shop filters, cart, search), **designed empty
  states** (empty cart, no search results, wishlist) that invite the next action.
- **WCAG AA**: text contrast ≥ 4.5:1 (≥ 3:1 large text/UI). Touch targets ≥ 44×44px.
  Progressive disclosure for secondary controls (filters, specs, variants).

## 5. Cinematic scroll & motion (details in the `motion-design` skill)

- Smooth inertia scrolling with **Lenis**.
- Scroll-scrubbed scenes with **GSAP ScrollTrigger**: pinned sections whose visuals respond
  to scroll position (product reveal, feature story).
- Subtle **parallax** depth, **kinetic typography** on hero/section headers,
  **View Transitions** between states/pages where supported.
- Spend boldness in one place per page: one signature scene, everything else calm.
- `prefers-reduced-motion: reduce` → no smooth-scroll hijack, no scrub/parallax,
  instant or opacity-only transitions. Mandatory, not optional.

## Dark mode ("night harbour")

- `html[data-vela-theme="dark"]`, set before first paint by `views/dark_mode.xml` (saved choice
  in `localStorage['vela-theme']`, else OS preference). Header toggle: `static/src/js/theme_toggle.js`.
- Our components switch through tokens. Odoo-native UI compiles fixed colours, so it is
  re-pointed in `static/src/scss/dark.scss`. Any new Odoo widget you style: check it in dark too.
- Product photos keep a light plinth in dark mode. Never `mix-blend-mode: multiply` an image
  that carries its own background over a dark surface (it darkens). Blend only inside a plinth wrapper.

## Definition of done for any visible change

Screenshots at 375 / 768 / 1440 px, light + dark, keyboard-only pass, reduced-motion pass,
contrast checked, `ui-critic` run with no blocking findings.
