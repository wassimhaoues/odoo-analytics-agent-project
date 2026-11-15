import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const KEY = "vela-theme";
const root = document.documentElement;
const current = () => (root.getAttribute("data-vela-theme") === "dark" ? "dark" : "light");
const ICONS = {
    // shown icon = the mode you switch TO
    dark: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z"/></svg>',
    light: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/></svg>',
};

/** Light / dark ("night harbour") toggle, added next to the header icons. */
export class VelaThemeToggle extends Interaction {
    static selector = "header#top";

    start() {
        const targets = this.el.querySelectorAll(
            "#o_main_nav ul.navbar-nav.align-items-center, .o_header_mobile_buttons_wrap");
        this.buttons = [...targets].map((ul) => {
            const li = document.createElement("li");
            li.className = "vela-theme-toggle-item";
            li.innerHTML = '<button type="button" class="vela-theme-toggle o_navlink_background" data-track="header.theme.toggle" data-track-type="click"></button>';
            this.insert(li, ul, "afterbegin");
            const btn = li.querySelector("button");
            this.addListener(btn, "click", () => this.toggle());
            return btn;
        });
        this.render();
    }

    render() {
        const next = current() === "dark" ? "light" : "dark";
        for (const btn of this.buttons) {
            btn.innerHTML = ICONS[next];
            btn.setAttribute("aria-label", next === "dark" ? "Switch to dark mode" : "Switch to light mode");
            btn.setAttribute("aria-pressed", String(current() === "dark"));
            btn.dataset.trackValue = next;
        }
    }

    toggle() {
        const next = current() === "dark" ? "light" : "dark";
        const apply = () => {
            root.setAttribute("data-vela-theme", next);
            this.render();
        };
        try { localStorage.setItem(KEY, next); } catch { /* private mode: session-only choice */ }
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (document.startViewTransition && !reduce) {
            document.startViewTransition(apply);     // smooth cross-fade between themes
        } else {
            apply();
        }
    }
}

registry.category("public.interactions").add("vela_theme.theme_toggle", VelaThemeToggle);
