import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

// Odoo-core header/footer controls we don't template ourselves get their data-track ids here,
// so the tracking contract covers them without overriding core templates.
const HEADER_TRACKS = [
    [".o_wsale_my_cart a", "header.cart.open", "click"],
    [".o_wsale_my_wish a", "header.wishlist.open", "click"],
    [".o_search_btn", "header.search.open", "click"],
    [".oe_search_button", "header.search.submit", "submit"],
    [".o_header_language_selector .dropdown-toggle", "header.language.toggle", "click"],
    [".js_change_lang", "header.language.select", "click"],
    [".o_nav_link_btn", "header.account.sign_in", "click"],
    ["header [data-bs-toggle='offcanvas']", "header.menu.open", "click"],
    ["header .offcanvas .btn-close", "header.menu.close", "click"],
    // footer: Odoo-core legal links
    ["footer#bottom a[href='/website/cookie-policy']", "footer.legal.cookie_policy", "click"],
    ["footer#bottom .o_cookies_bar_toggle", "footer.legal.cookie_preferences", "click"],
];

export class VelaTrackingAnnotations extends Interaction {
    static selector = "#wrapwrap";

    setup() {
        for (const [selector, track, type] of HEADER_TRACKS) {
            for (const el of this.el.querySelectorAll(selector)) {
                if (el.dataset.track) {
                    continue;
                }
                el.dataset.track = track;
                el.dataset.trackType = type;
                if (el.classList.contains("js_change_lang")) {
                    el.dataset.trackLang = el.dataset.url_code || el.getAttribute("hreflang") || "";
                }
            }
        }
    }
}

registry.category("public.interactions").add("vela_theme.tracking_annotations", VelaTrackingAnnotations);
