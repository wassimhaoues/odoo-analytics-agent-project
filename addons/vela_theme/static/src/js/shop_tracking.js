import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

// Tracking contract for website_sale UI we don't template ourselves.
// SKUs come from data-vela-sku (views/shop.xml); positions are 1-based grid indexes.
const set = (el, track, type, extra = {}) => {
    if (!el || el.dataset.track) {
        return;
    }
    el.dataset.track = track;
    el.dataset.trackType = type;
    Object.assign(el.dataset, extra);
};

/** Shop grid tiles: open, add to cart, wishlist, compare. */
export class VelaShopTileTracking extends Interaction {
    static selector = "#o_wsale_products_grid";

    setup() {
        this.el.querySelectorAll(".oe_product_cart").forEach((tile, i) => {
            const extra = { trackProduct: tile.dataset.velaSku || "", trackPosition: String(i + 1) };
            tile.querySelectorAll("a[href^='/shop/']").forEach((a) => set(a, "shop.product.open", "click", extra));
            set(tile.querySelector("button[name='add_to_cart']"), "shop.product.add_to_cart", "click", extra);
            set(tile.querySelector(".o_add_wishlist"), "shop.product.wishlist", "click", extra);
            set(tile.querySelector(".o_add_compare"), "shop.product.compare", "click", extra);
        });
    }
}

/** Shop chrome: category filmstrip, sorting, filters, pagination. */
export class VelaShopChromeTracking extends Interaction {
    static selector = "#wrap .o_wsale_products_page, #products_grid";

    setup() {
        this.el.querySelectorAll(".o_wsale_filmstrip_link").forEach((a, i) => {
            const slug = (a.getAttribute("href") || "").split("/").pop().replace(/-\d+$/, "");
            set(a, `shop.filmstrip.${slug.replace(/-/g, "_")}`, "click", { trackCategory: slug, trackPosition: String(i + 1) });
        });
        this.el.querySelectorAll(".o_sortby_dropdown .dropdown-item").forEach((a) => {
            const order = new URL(a.href, location.origin).searchParams.get("order") || "";
            set(a, `shop.sort.${order.replace(/\s+/g, "_")}`, "click");
        });
        set(this.el.querySelector(".o_sortby_dropdown .dropdown-toggle"), "shop.sort.open", "click");
        this.el.querySelectorAll("[data-bs-target='#o_wsale_offcanvas'], button.d-lg-none").forEach((b) =>
            set(b, "shop.filters.open", "click"));
        this.el.querySelectorAll(".pagination a").forEach((a) => set(a, "shop.pagination.page", "click"));
        set(this.el.querySelector(".o_wsale_products_searchbar_form .oe_search_button"), "shop.search.submit", "submit");
    }
}

/** Filter sidebar / offcanvas: attribute values, categories, price. */
export class VelaShopFilterTracking extends Interaction {
    static selector = "#products_grid_before, #o_wsale_offcanvas";

    setup() {
        this.el.querySelectorAll(".accordion-button").forEach((b) => {
            const name = (b.textContent || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
            set(b, `filters.attribute.${name}`, "click");
        });
        this.el.querySelectorAll("input[name='attribute_value'], input[name='tags']").forEach((input) =>
            set(input, "filters.value.toggle", "click", { trackValue: input.value }));
        this.el.querySelectorAll("a[href*='/shop/category/']").forEach((a) => {
            const slug = (a.getAttribute("href") || "").split("/").pop().replace(/-\d+$/, "");
            set(a, "filters.category.select", "click", { trackCategory: slug });
        });
    }
}

/** Product page: add to cart, buy now, wishlist, compare, variant changes, gallery. */
export class VelaProductPageTracking extends Interaction {
    static selector = "#product_detail";

    setup() {
        const sku = this.el.querySelector("#product_details")?.dataset.velaSku || "";
        const extra = { trackProduct: sku };
        set(this.el.querySelector("#add_to_cart, #add_to_cart_wrap button.btn-primary"), "product.add_to_cart", "click", extra);
        set(this.el.querySelector(".o_we_buy_now, a[name='buy_now'], button[name='buy_now']"), "product.buy_now", "click", extra);
        set(this.el.querySelector(".o_add_wishlist_dyn, .o_add_wishlist"), "product.wishlist", "click", extra);
        set(this.el.querySelector(".o_add_compare_dyn, .o_add_compare"), "product.compare", "click", extra);
        this.el.querySelectorAll(".js_variant_change").forEach((input) =>
            set(input, "product.variant.change", "click", extra));
        this.el.querySelectorAll(".carousel-indicators li, .carousel-control-prev, .carousel-control-next").forEach((el) =>
            set(el, "product.gallery.navigate", "click", extra));
        this.el.querySelectorAll(".o_wsale_breadcrumb a").forEach((a) => set(a, "product.breadcrumb.open", "click"));
        this.el.querySelectorAll(".o_product_tags a").forEach((a) => set(a, "product.tag.open", "click", extra));
    }
}

/**
 * Rules for controls that are static OR inserted later by Odoo (dynamic product snippets,
 * quantity widgets, ribbon filters). Re-applied on DOM changes. Anything interactive that
 * no rule covers gets a fallback id plus data-track-auto="1", so analytics still sees
 * the click and `scripts/page_check.mjs` reports it as a gap to name properly.
 */
const RULES = [
    [".o_wsale_ribbon_filter", "filters.ribbon.toggle", "click", (el) => ({ trackValue: el.textContent.trim().toLowerCase() })],
    ["#o_wsale_offcanvas .btn-link, #products_grid_before .btn-link", "filters.clear", "click"],
    ["#o_wsale_offcanvas .btn-primary", "filters.apply", "click"],
    [".css_quantity a, .css_quantity button", "product.quantity.change", "click"],
    [".o_product_variant_preview", "shop.product.variant_preview", "click"],
    [".s_dynamic_snippet_products a[href^='/shop/']", "recommend.product.open", "click"],
    [".s_dynamic_snippet_products button[name='add_to_cart']", "recommend.product.add_to_cart", "click"],
    [".s_dynamic_snippet_products .o_add_wishlist", "recommend.product.wishlist", "click"],
    [".carousel-control-prev, .carousel-control-next, .carousel-indicators li", "carousel.navigate", "click"],
    ["#product_detail a[href*='/shop/compare'], .o_add_compare_dyn", "product.compare", "click"],
    // back-in-stock subscription: demand signal for the AI agent (step 4)
    ["#out_of_stock_buttons_wrapper a, #out_of_stock_buttons_wrapper button", "product.stock.notify_open", "click"],
    ["#stock_notification_input_wrapper button, #stock_notification_input_wrapper a", "product.stock.notify_submit", "submit"],
    ["#contact_us_wrapper a, #contact_us_wrapper button", "product.contact", "click"],
    ["#o_wsale_product_cta_section owl-component a, #o_wsale_product_cta_section owl-component button", "product.pickup.store_info", "click"],
    [".s_dynamic_snippet_products .o_add_compare, .s_dynamic_snippet_products [data-action='o_comparelist']", "recommend.product.compare", "click"],
    // cookie consent (bar is injected after load)
    ["#cookies-consent-essential", "consent.essential_only", "click"],
    ["#cookies-consent-all", "consent.accept_all", "click"],
    ["#website_cookies_bar .o_cookies_bar_close", "consent.close", "click"],
    ["#website_cookies_bar .o_cookies_bar_text_policy", "consent.policy_open", "click"],
    // cart & checkout
    [".o_wizard a", "checkout.step.open", "click"],
    [".o_cart_product a[href^='/shop/']", "cart.product.open", "click"],
    [".o_cart_product .js_delete_product, .o_cart_product a[name='o_cart_line_remove']", "cart.line.remove", "click"],
    [".o_cart_product .o_wish_later, .o_cart_product a[name='save_for_later']", "cart.line.save_for_later", "click"],
    ["#suggested_products button, #suggested_products a.btn", "cart.suggested.add_to_cart", "click"],
    ["#suggested_products a[href^='/shop/']", "cart.suggested.open", "click"],
    [".o_total_card a[href='/shop/checkout'], .o_total_card a[href*='/shop/checkout'], .o_total_card a[name='website_sale_main_button']", "cart.checkout", "click"],
    [".o_total_card a[href='/shop'], .o_total_card a[href*='continue']", "cart.continue_shopping", "click"],
    [".o_total_card form button, .o_total_card .a-submit", "cart.coupon.apply", "submit"],
    ["#quick_reorder_button, [data-bs-target='#quick_reorder_sidebar']", "cart.quick_reorder.open", "click"],
    ["#quick_reorder_sidebar .btn-close", "cart.quick_reorder.close", "click"],
    ["#quick_reorder_sidebar a", "cart.quick_reorder.select", "click"],
    ["form.address_autoformat button[type='submit'], form.address_autoformat .a-submit", "checkout.address.submit", "submit"],
    ["a[name='website_sale_main_button'], .o_cta_navigation_container a.btn-primary", "checkout.next", "click"],
    [".o_cta_navigation_container a:not(.btn)", "checkout.back", "click"],
    ["#o_payment_form_pay, button[name='o_payment_submit_button']", "checkout.payment.submit", "submit"],
    [".o_mobile_summary button", "checkout.summary.toggle", "click"],
    [".o_mobile_summary a:not(.btn)", "checkout.back", "click"],
    ["#o_cart_summary_offcanvas .btn-link", "checkout.summary.coupon_open", "click"],
    ["#o_cart_summary_offcanvas .btn-close", "checkout.summary.close", "click"],
    // variant/options dialog opened by "Add to cart": the key conversion clicks.
    // SKU = the product whose button opened the dialog (remembered on click).
    ["button[name='website_sale_product_configurator_continue_button']", "product.configurator.add_to_cart", "click", () => lastSkuExtra()],
    ["button[name='website_sale_product_configurator_checkout_button']", "product.configurator.checkout", "click", () => lastSkuExtra()],
    ["button[name='sale_product_configurator_cancel_button']", "product.configurator.cancel", "click", () => lastSkuExtra()],
    [".modal:has(button[name^='website_sale_product_configurator']) .modal-header .btn-close", "product.configurator.close", "click", () => lastSkuExtra()],
    [".modal:has(button[name^='website_sale_product_configurator']) .js_variant_change", "product.configurator.variant_change", "click", () => lastSkuExtra()],
    // customer accounts (login / signup / reset)
    ["form.oe_login_form button[type='submit']", "account.login.submit", "submit"],
    ["form.oe_signup_form button[type='submit']", "account.signup.submit", "submit"],
    ["form.oe_reset_password_form button[type='submit']", "account.password.reset_submit", "submit"],
    ["form.oe_login_form .input-group button, form.oe_signup_form .input-group button", "account.password.toggle_visibility", "click"],
    [".passkey_login_link a, a.passkey_login_link", "account.login.passkey", "click"],
    [".o_auth_oauth_providers a", "account.login.oauth", "click"],
    ["a[href^='/web/signup']", "account.signup.open", "click"],
    ["a[href^='/web/reset_password']", "account.password.reset_open", "click"],
    ["form.oe_signup_form a[href^='/web/login'], form.oe_reset_password_form a[href^='/web/login']", "account.login.open", "click"],
    // empty states (no-results page uses its own area)
    [".vela-empty__cats a", "empty.category.open", "click"],
];
let lastSku = "";
const lastSkuExtra = () => (lastSku ? { trackProduct: lastSku } : {});
const INTERACTIVE = "a[href], button, [role='button'], input[type='submit']";

export class VelaDynamicTracking extends Interaction {
    static selector = "#wrapwrap";

    start() {
        // remember which product an add-to-cart click was for (dialogs don't carry the SKU)
        this.addListener(document, "click", (ev) => {
            const sku = ev.target.closest?.("[data-track-product]")?.dataset.trackProduct;
            if (sku) {
                lastSku = sku;
            }
        }, { capture: true });
        this.apply();
        let timer = null;
        this.observer = new MutationObserver(() => {
            clearTimeout(timer);
            timer = setTimeout(() => this.apply(), 150);
        });
        // Odoo mounts dialogs outside #wrapwrap, so watch the whole body
        this.observer.observe(document.body, { childList: true, subtree: true });
        this.registerCleanup(() => {
            clearTimeout(timer);
            this.observer.disconnect();
        });
    }

    apply() {
        for (const [selector, track, type, extraFn] of RULES) {
            document.querySelectorAll(selector).forEach((el) => {
                const sku = el.closest("[data-vela-sku]")?.dataset.velaSku;
                set(el, track, type, { ...(extraFn ? extraFn(el) : {}), ...(sku ? { trackProduct: sku } : {}) });
            });
        }
        this.el.querySelectorAll("main " + INTERACTIVE.split(", ").join(", main ")).forEach((el) => {
            if (el.closest("[data-track]") || el.closest(".o_not_editable.oe_structure, .o_frontend_to_backend_nav")) {
                return;
            }
            const area = el.closest("section[id], div[id]")?.id || "page";
            set(el, `auto.${area.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}`, "click", { trackAuto: "1" });
        });
    }
}

const interactions = registry.category("public.interactions");
interactions.add("vela_theme.shop_tile_tracking", VelaShopTileTracking);
interactions.add("vela_theme.shop_chrome_tracking", VelaShopChromeTracking);
interactions.add("vela_theme.shop_filter_tracking", VelaShopFilterTracking);
interactions.add("vela_theme.product_page_tracking", VelaProductPageTracking);
interactions.add("vela_theme.dynamic_tracking", VelaDynamicTracking);
