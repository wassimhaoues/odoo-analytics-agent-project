---
name: motion-design
description: Cinematic motion for the Vela Tech Odoo website — Lenis smooth scroll, GSAP ScrollTrigger pinned/scrubbed scenes, parallax, kinetic typography, View Transitions, micro-interactions — implemented as Odoo 20 Interactions with reduced-motion and performance guarantees. Use when adding or reviewing any animation, scroll effect or transition in addons/vela_theme.
---

# Motion design for vela_theme

Motion must feel weighted, intentional and calm, like a well-edited film, not a slideshow.
Read `rules/design-system.md` §5 first. One **signature scene** per page; everything else is
quiet micro-feedback.

## Stack (vendored, never CDN)

| Lib | Use | Where |
|---|---|---|
| Lenis | inertia smooth scroll | `addons/vela_theme/static/lib/lenis-<ver>/` |
| GSAP core + ScrollTrigger (+ SplitText if needed) | scroll scenes, scrub, pin, kinetic type | `addons/vela_theme/static/lib/gsap-<ver>/` |
| View Transitions API (native) | state/page transitions | progressive enhancement only |
| CSS scroll-driven animations (native) | cheap reveals where supported | `animation-timeline: view()` with fallback |

Vendor each lib with its LICENSE file and pin the version in the folder name. Add them to
`web.assets_frontend` **before** our interactions in the manifest `assets` list. Check the
current GSAP license terms when vendoring and record them in an ADR.

## Odoo 20 integration pattern (verified API: `@web/public/interaction`)

```js
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const inEditor = () => document.body.classList.contains("editor_enable");

export class VelaHeroScene extends Interaction {
    static selector = ".s_vela_hero";            // one interaction per snippet/section

    start() {
        if (reduceMotion() || inEditor()) return;   // static, fully readable fallback
        const { gsap, ScrollTrigger } = window;
        gsap.registerPlugin(ScrollTrigger);
        this.ctx = gsap.context(() => {              // scopes all tweens to this.el
            gsap.timeline({
                scrollTrigger: { trigger: this.el, start: "top top", end: "+=150%",
                                 scrub: 0.6, pin: true, anticipatePin: 1 },
            })
            .from(".s_vela_hero__title .word", { yPercent: 110, stagger: 0.04, ease: "power3.out" })
            .to(".s_vela_hero__product", { scale: 1.08, rotateY: -12, ease: "none" }, 0);
        }, this.el);
        this.registerCleanup(() => this.ctx.revert());   // editor re-renders: always clean up
    }
}
registry.category("public.interactions").add("vela_theme.hero_scene", VelaHeroScene);
// Do NOT also register in "public.interactions.edit": interactions absent from that
// registry don't run inside the website editor, which is exactly what scroll scenes need.
// The inEditor() check above is a second line of defence.
```

Lenis is a **single** site-wide interaction on `#wrapwrap` (or `html`) that:
- skips when reduced motion or the editor is active,
- drives ScrollTrigger: `lenis.on("scroll", ScrollTrigger.update)` and
  `gsap.ticker.add((t) => lenis.raf(t * 1000))`, `gsap.ticker.lagSmoothing(0)`,
- respects in-page anchors and Odoo's modals/offcanvas (stop Lenis while they're open),
- `registerCleanup(() => lenis.destroy())`.

## Motion vocabulary (use these, don't invent per page)

| Token | Duration | Ease | Use |
|---|---|---|---|
| `--dur-instant` | 80ms | linear | press feedback |
| `--dur-fast` | 160ms | `cubic-bezier(.2,.8,.2,1)` | hover, focus, icon morph |
| `--dur-base` | 240ms | same | menus, drawers, toasts |
| `--dur-slow` | 480ms | `cubic-bezier(.16,1,.3,1)` | section reveal, page enter |
| scrub | 0.4–0.8 | `none` inside scrubbed timelines | scroll scenes |

Exit faster than enter. Animate only `transform`, `opacity`, `filter`, `clip-path`.
Never animate `width/height/top/left`.

## Scene ideas that fit a tech store

- **Hero**: product rotates and scales with scroll while the headline splits in word by word (kinetic type).
- **Pinned "inside the device"** scene: spec callouts appear along the scroll scrub.
- **Bento grid**: tiles lift with subtle parallax at different depths (`yPercent` ±6–10).
- **Category rail**: horizontal scroll driven by vertical scroll (pin + `x` scrub).
- **Add to cart**: product thumbnail flies to the cart icon (GSAP Flip or a cloned element), badge count ticks.
- **Page/state changes**: `document.startViewTransition` for filter/sort updates; CSS
  `@view-transition { navigation: auto; }` for same-origin page navigation where supported.

## Reduced motion & accessibility (mandatory)

- `prefers-reduced-motion: reduce` → no Lenis, no pin/scrub/parallax, no kinetic splitting.
  Content is in its final state. Keep only opacity fades ≤ 160ms.
- Split text must keep the original text accessible (`aria-label` on the parent, split spans `aria-hidden`).
- Never trap scroll. Pinned sections must be skippable by keyboard (focus order intact).
- Nothing important appears *only* through motion.

## Performance budget

- No animation work before first paint. Init interactions after load. Hero LCP image is not animated in.
- Under ~6 simultaneous ScrollTriggers per viewport. Call `ScrollTrigger.refresh()` after images/fonts load.
- 60fps on a mid-range laptop. Check the Performance panel: no long tasks > 50ms from scroll handlers.
- Test with CPU 4× throttling. If a scene stutters, simplify it rather than fight it.

## Review checklist

- [ ] Works and reads correctly with motion **off**
- [ ] Editor mode: no scroll hijack, no pinned sections, content editable
- [ ] All tweens scoped (`gsap.context`) and reverted in `registerCleanup`
- [ ] Only transform/opacity animated, no layout shift (CLS < 0.1)
- [ ] Mobile (375px): scenes simplified or disabled, no horizontal overflow
- [ ] `data-track` attributes untouched by DOM splitting (tracking-contract.md)
