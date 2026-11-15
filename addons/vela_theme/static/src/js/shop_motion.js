/* global gsap, ScrollTrigger */
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const inEditor = () => document.body.classList.contains("editor_enable");
const motionOK = () => !reduceMotion() && !inEditor() && window.gsap;

const ADD_BUTTONS = "button[name='add_to_cart'], #add_to_cart, #add_to_cart_wrap button.btn-primary";
const FLY_WINDOW_MS = 6000;   // an add can wait on the variant configurator dialog

/**
 * Add-to-cart feedback, keyed on Odoo's own cart counter (.my_cart_quantity) so it only
 * fires when the cart really changed. Badge bump always (CSS, reduced-motion safe);
 * the product image flies to the cart icon when the add followed a click on a product.
 */
export class VelaCartFeedback extends Interaction {
    static selector = "header#top";

    start() {
        this.lastClick = null;
        this.badges = [...this.el.querySelectorAll(".my_cart_quantity")];
        this.count = this.readCount();
        this.addListener(document, "click", (ev) => {
            const btn = ev.target.closest?.(ADD_BUTTONS);
            if (!btn) {
                return;
            }
            const scope = btn.closest(".oe_product_cart, #product_detail");
            const img = scope?.querySelector(".oe_product_image_img, .carousel-item.active img, .product_detail_img");
            this.lastClick = img ? { img, at: Date.now() } : null;
        }, { capture: true });
        this.observer = new MutationObserver(() => this.onCartChange());
        this.badges.forEach((b) => this.observer.observe(b, { childList: true, characterData: true, subtree: true }));
        this.registerCleanup(() => this.observer.disconnect());
    }

    readCount() {
        return Math.max(0, ...this.badges.map((b) => parseInt(b.textContent, 10) || 0));
    }

    onCartChange() {
        const count = this.readCount();
        const added = count > this.count;
        this.count = count;
        if (!added) {
            return;
        }
        this.badges.forEach((b) => {
            b.classList.remove("vela-bump");
            void b.offsetWidth;            // restart the CSS animation
            b.classList.add("vela-bump");
        });
        if (this.lastClick && Date.now() - this.lastClick.at < FLY_WINDOW_MS && motionOK()) {
            this.fly(this.lastClick.img);
        }
        this.lastClick = null;
    }

    fly(img) {
        const target = [...this.el.querySelectorAll(".o_wsale_my_cart")].find((el) => el.offsetParent);
        if (!target || !img.getBoundingClientRect().width) {
            return;
        }
        const from = img.getBoundingClientRect();
        const to = target.getBoundingClientRect();
        const ghost = img.cloneNode();
        ghost.removeAttribute("loading");
        Object.assign(ghost.style, {
            position: "fixed", left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`,
            height: `${from.height}px`, objectFit: "contain", zIndex: 2000, pointerEvents: "none",
            borderRadius: "24px", background: "var(--plinth)", boxShadow: "var(--shadow-3)",
        });
        document.body.appendChild(ghost);
        const size = 32;
        gsap.to(ghost, {
            left: to.left + to.width / 2 - size / 2, top: to.top + to.height / 2 - size / 2,
            width: size, height: size, borderRadius: size, opacity: 0.4,
            duration: 0.7, ease: "power3.in", onComplete: () => ghost.remove(),
        });
        this.registerCleanup(() => ghost.remove());
    }
}

/** Shop grid: tiles rise in as they enter the viewport (batched). */
export class VelaShopGridReveal extends Interaction {
    static selector = "#o_wsale_products_grid";

    start() {
        if (!motionOK() || !window.ScrollTrigger) {
            return;
        }
        gsap.registerPlugin(ScrollTrigger);
        const tiles = this.el.querySelectorAll(".oe_product");
        this.ctx = gsap.context(() => {
            gsap.set(tiles, { autoAlpha: 0, y: 24 });
            ScrollTrigger.batch(tiles, {
                start: "top 92%",
                once: true,
                onEnter: (batch) => gsap.to(batch, { autoAlpha: 1, y: 0, duration: 0.6, stagger: 0.06, ease: "power3.out" }),
            });
        }, this.el);
        this.registerCleanup(() => this.ctx.revert());
    }
}

const interactions = registry.category("public.interactions");
interactions.add("vela_theme.cart_feedback", VelaCartFeedback);
interactions.add("vela_theme.shop_grid_reveal", VelaShopGridReveal);
