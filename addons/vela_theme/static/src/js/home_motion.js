/* global gsap, ScrollTrigger, Lenis */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

// Motion rules: .claude/skills/motion-design/SKILL.md
// - nothing runs with prefers-reduced-motion or inside the website editor
//   (these interactions are not registered in "public.interactions.edit")
// - every tween is scoped with gsap.context and reverted in registerCleanup
const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const inEditor = () => document.body.classList.contains("editor_enable");
const motionOK = () => !reduceMotion() && !inEditor() && window.gsap && window.ScrollTrigger;
const isDesktop = () => window.matchMedia("(min-width: 992px)").matches;

/** Site-wide inertia scrolling (Lenis) driving ScrollTrigger. */
export class VelaSmoothScroll extends Interaction {
    static selector = "#wrapwrap";

    start() {
        if (!motionOK() || !window.Lenis) {
            return;
        }
        gsap.registerPlugin(ScrollTrigger);
        ScrollTrigger.config({ ignoreMobileResize: true });   // no re-layout when mobile URL bar hides
        const lenis = new Lenis({
            lerp: 0.1,
            // let modals, offcanvas, dropdowns and scrollable rails scroll natively
            prevent: (node) => !!node.closest?.(".modal, .offcanvas, .dropdown-menu, .s_vela_rail__track, .o_search_input_group"),
        });
        const raf = (time) => lenis.raf(time * 1000);
        lenis.on("scroll", ScrollTrigger.update);
        gsap.ticker.add(raf);
        gsap.ticker.lagSmoothing(0);
        this.registerCleanup(() => {
            gsap.ticker.remove(raf);
            lenis.destroy();
        });
    }
}

/** Homepage hero: kinetic headline, then the doorway opens as you scroll (pinned + scrubbed). */
export class VelaHeroScene extends Interaction {
    static selector = ".s_vela_hero";

    start() {
        if (!motionOK()) {
            return;
        }
        gsap.registerPlugin(ScrollTrigger);
        const el = this.el;
        this.ctx = gsap.context(() => {
            const intro = gsap.timeline({ defaults: { ease: "power4.out" } });
            intro.from(".vela-word > span", { yPercent: 110, duration: 1, stagger: 0.07 })
                .from(".s_vela_hero__arch", { scaleY: 0.2, transformOrigin: "50% 100%", duration: 1.2, ease: "expo.out" }, 0)
                .from(".s_vela_hero__product", { scale: 0.6, autoAlpha: 0, duration: 1.2, ease: "expo.out" }, 0.15)
                .from([".s_vela_hero__lede", ".s_vela_hero__cta", ".s_vela_hero__meta", ".s_vela_hero__tag"],
                    { autoAlpha: 0, y: 16, duration: 0.8, stagger: 0.08, ease: "power3.out" }, 0.4);

            if (isDesktop()) {
                gsap.timeline({
                    // pinSpacing:false: the next sections slide over the pinned hero (no blank viewport after it)
                    scrollTrigger: {
                        trigger: el, start: "top top+=88", end: "+=100%", scrub: 0.6, pin: true, pinSpacing: false, anticipatePin: 1,
                        // perf: drop expensive paint effects only while the scene is playing
                        onToggle: (self) => document.documentElement.classList.toggle("vela-scene-active", self.isActive),
                    },
                })
                    // explicit start values: this timeline is built while the intro is still
                    // mid-flight, so plain .to() would capture the intro's squashed state.
                    // The doorway opens from its centre, not the intro's bottom origin.
                    .fromTo(".s_vela_hero__arch", { scaleX: 1, scaleY: 1, transformOrigin: "50% 50%" },
                        { scaleX: 4.2, scaleY: 4.2, ease: "power2.inOut", duration: 1, immediateRender: false }, 0)
                    .fromTo(".s_vela_hero__product", { rotate: 0, scale: 1, yPercent: 0, autoAlpha: 1 },
                        { rotate: -18, scale: 1.25, yPercent: -6, ease: "none", duration: 1, immediateRender: false }, 0)
                    .fromTo(".s_vela_hero__copy", { autoAlpha: 1, x: 0 },
                        { autoAlpha: 0, x: -64, ease: "power1.in", duration: 0.5, immediateRender: false }, 0)
                    .fromTo(".s_vela_hero__tag", { autoAlpha: 1, y: 0 },
                        { autoAlpha: 0, y: 32, duration: 0.3, immediateRender: false }, 0)
                    // walk through the door: blue and product dissolve into the next section
                    .to([".s_vela_hero__arch", ".s_vela_hero__product"], { autoAlpha: 0, duration: 0.25, ease: "power1.in" }, 0.8);
            }
        }, el);
        // fonts/images change layout: recalc trigger positions once loaded
        const refresh = () => ScrollTrigger.refresh();
        window.addEventListener("load", refresh, { once: true });
        this.registerCleanup(() => {
            window.removeEventListener("load", refresh);
            document.documentElement.classList.remove("vela-scene-active");
            this.ctx.revert();
        });
    }
}

/** Section headings rise in; bento tiles drift at different depths (parallax). */
export class VelaHomeReveal extends Interaction {
    static selector = ".s_vela_home";

    start() {
        if (!motionOK()) {
            return;
        }
        gsap.registerPlugin(ScrollTrigger);
        this.ctx = gsap.context(() => {
            gsap.utils.toArray(".vela-section-head h2").forEach((h) =>
                gsap.from(h, { yPercent: 40, autoAlpha: 0, duration: 0.9, ease: "power3.out",
                    scrollTrigger: { trigger: h, start: "top 85%" } }));
            if (isDesktop()) {
                gsap.utils.toArray("[data-vela-depth]").forEach((tile) => {
                    const d = Number(tile.dataset.velaDepth) * 6;
                    gsap.fromTo(tile, { y: d }, { y: -d, ease: "none",
                        scrollTrigger: { trigger: tile, start: "top bottom", end: "bottom top", scrub: true } });
                });
            }
        }, this.el);
        // perf: the brand marquee only runs while it is on screen
        const marquee = this.el.querySelector(".s_vela_brands");
        if (marquee && "IntersectionObserver" in window) {
            const io = new IntersectionObserver(([entry]) => marquee.classList.toggle("is-offscreen", !entry.isIntersecting));
            io.observe(marquee);
            this.registerCleanup(() => io.disconnect());
        }
        this.registerCleanup(() => this.ctx.revert());
    }
}

const interactions = registry.category("public.interactions");
interactions.add("vela_theme.smooth_scroll", VelaSmoothScroll);
interactions.add("vela_theme.hero_scene", VelaHeroScene);
interactions.add("vela_theme.home_reveal", VelaHomeReveal);
