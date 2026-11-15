# 0006. Motion with vendored GSAP 3.12.5 + ScrollTrigger and Lenis 1.1.13

- Status: accepted
- Date: 2026-11-15

## Context
The owner's brief asks for cinematic scroll: inertia scrolling, scroll-scrubbed pinned
scenes, parallax and kinetic type, with reduced-motion respected. CSS scroll-driven
animations alone can't pin and scrub reliably across browsers yet.

## Decision
- **GSAP 3.12.5 + ScrollTrigger** for timelines, pinning and scrubbing. Licensed under
  GreenSock's "Standard No Charge" licence (header in `gsap.min.js`, terms at
  https://gsap.com/standard-license). It's free to use, but not OSI open source. Fine for this
  non-commercial study project. Re-check the terms before any commercial use.
- **Lenis 1.1.13** (MIT) for inertia scrolling, driving ScrollTrigger through `gsap.ticker`.
- Both are vendored in `addons/vela_theme/static/lib/<lib>-<version>/` with their licence and
  README, loaded in `web.assets_frontend` before our interactions. No CDN.
- Behaviour lives in Odoo 20 Interactions (`static/src/js/home_motion.js`). They're not
  registered for the editor, every tween is scoped with `gsap.context` and reverted on cleanup,
  nothing runs under `prefers-reduced-motion`, and the pinned scene runs only from 992px up.
- Lenis leaves native scrolling to modals, offcanvas, dropdowns and horizontal rails.

## Consequences
About 130 KB of JS (minified) on every page. The static, final-state layout must always be
complete and readable without JS. Animations use `fromTo` with explicit start values when
timelines overlap (lesson from the hero: a `.to()` built during the intro captured a
half-animated state).

## Alternatives considered
- CSS scroll-driven animations only: no reliable pinning or scrub easing, uneven support.
- Framer Motion / Motion One: React-oriented or no pin/scrub equivalent for server-rendered QWeb.
