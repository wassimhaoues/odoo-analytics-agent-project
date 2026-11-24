import { cookie } from "@web/core/browser/cookie";
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

/**
 * vela_analytics browser tracker (docs/plans/0001-vela-analytics.md §4, §6).
 *
 * - Consent: Odoo's cookie bar. Undecided → events wait in memory (max 20, never sent).
 *   "I agree" → sent. "Only essentials" / leaving the page → dropped (D9).
 * - Session: random UUID in the optional cookie `vela_session`, 30 min sliding expiry.
 * - Batches go to /vela/analytics/events with sendBeacon (fetch keepalive as fallback).
 */
const ENDPOINT = "/vela/analytics/events";
const SESSION_COOKIE = "vela_session";
const SESSION_TTL = 30 * 60;
const FLUSH_MS = 5000;
const FLUSH_SIZE = 20;
const HOLD_MAX = 20;
const CHECKOUT_PATHS = ["/shop/checkout", "/shop/address"];

const queue = [];
let consent = "unknown"; // "unknown" | "granted" | "denied"
let timer = null;

const uuid = () =>
    globalThis.crypto?.randomUUID?.() ||
    "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
        (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
    );

function readConsent() {
    if (!document.getElementById("cookies-consent-essential")) {
        return "granted"; // cookie bar disabled on this website: Odoo treats optional as allowed
    }
    try {
        const value = JSON.parse(decodeURIComponent(cookie.get("website_cookies_bar") || "null"));
        if (value && typeof value === "object" && "optional" in value) {
            return value.optional ? "granted" : "denied";
        }
    } catch {
        // malformed cookie: same as undecided
    }
    return "unknown";
}

function session() {
    let id = cookie.get(SESSION_COOKIE);
    if (!/^[0-9a-f-]{36}$/.test(id || "")) {
        id = uuid();
    }
    cookie.set(SESSION_COOKIE, id, SESSION_TTL, "optional"); // sliding 30 min window
    return id;
}

function utm() {
    const params = new URLSearchParams(location.search);
    const out = {};
    for (const key of ["source", "medium", "campaign"]) {
        const value = (params.get(`utm_${key}`) || "").toLowerCase().slice(0, 64);
        if (/^[a-z0-9][a-z0-9_-]*$/.test(value)) {
            out[key] = value;
        }
    }
    return Object.keys(out).length ? out : undefined;
}

function base(event, extra = {}) {
    return {
        v: 1,
        event_id: uuid(),
        event,
        ts: new Date().toISOString(),
        page: location.pathname,
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        ...extra,
    };
}

function flush() {
    clearTimeout(timer);
    timer = null;
    if (consent !== "granted" || !queue.length) {
        return;
    }
    session(); // refresh the sliding cookie before the server reads it
    while (queue.length) {
        const body = JSON.stringify({ events: queue.splice(0, FLUSH_SIZE) });
        const blob = new Blob([body], { type: "application/json" });
        if (!navigator.sendBeacon?.(ENDPOINT, blob)) {
            fetch(ENDPOINT, { method: "POST", body, keepalive: true, credentials: "same-origin",
                headers: { "Content-Type": "application/json" } }).catch(() => {});
        }
    }
}

function track(event, extra) {
    if (consent === "denied") {
        return;
    }
    if (consent === "unknown") {
        if (queue.length < HOLD_MAX) {
            queue.push(base(event, extra)); // held in memory only, nothing leaves the browser
        }
        return;
    }
    queue.push(base(event, extra));
    if (queue.length >= FLUSH_SIZE) {
        flush();
    } else if (!timer) {
        timer = setTimeout(flush, FLUSH_MS);
    }
}

function dataOf(el) {
    const d = el.dataset;
    const extra = { track: d.track };
    if (d.trackProduct) {
        extra.product = d.trackProduct;
    }
    if (d.trackCategory) {
        extra.category = d.trackCategory;
    }
    const position = parseInt(d.trackPosition, 10);
    if (position > 0) {
        extra.position = position;
    }
    return extra;
}

function onClick(ev) {
    const el = ev.target.closest?.("[data-track]");
    if (!el || el.dataset.trackAuto || el.dataset.trackType === "view") {
        return; // auto.* fallbacks are gaps reported by page_check, not analytics
    }
    track("click", dataOf(el));
}

function watchCheckoutForm(it) {
    const seen = new Set();
    const report = (field) => {
        const name = (field?.name || "").toLowerCase().replace(/[^a-z0-9_]/g, "_").slice(0, 40);
        if (!name || seen.has(name)) {
            return;
        }
        seen.add(name);
        track("checkout_error", { error_code: "form_validation", field: /^[a-z_]/.test(name) ? name : undefined });
    };
    it.addListener(document, "invalid", (ev) => ev.target.closest?.("form") && report(ev.target), true);
    const form = document.querySelector("form.checkout_autoformat, form[action*='/shop/address']");
    if (form) {
        const observer = new MutationObserver((records) => {
            for (const r of records) {
                if (r.target.classList?.contains("is-invalid")) {
                    report(r.target);
                }
            }
        });
        observer.observe(form, { subtree: true, attributes: true, attributeFilter: ["class"] });
        it.registerCleanup(() => observer.disconnect());
    }
}

function start(it) {
    if (window.self !== window.top || document.body.classList.contains("editor_enable")) {
        return; // website builder preview: not a visitor
    }
    consent = readConsent();
    if (consent === "denied") {
        return;
    }
    it.addListener(document, "optionalCookiesAccepted", () => {
        // Odoo writes its consent cookie when the banner finishes closing, after this event.
        // Wait for it: the server re-checks consent, and our session cookie needs it too.
        let tries = 0;
        const waitForCookie = () => {
            if (readConsent() === "granted") {
                consent = "granted";
                flush();
            } else if (++tries < 50) {
                setTimeout(waitForCookie, 100);
            }
        };
        waitForCookie();
    });
    it.addListener(document, "optionalCookiesDenied", () => {
        consent = "denied";
        queue.length = 0;
    });
    it.addListener(document, "click", onClick, true);
    it.addListener(document, "visibilitychange", () => document.visibilityState === "hidden" && flush());
    it.addListener(window, "pagehide", flush);

    if (CHECKOUT_PATHS.includes(location.pathname)) {
        watchCheckoutForm(it);
    }
    if (pageTracked) {
        return;
    }
    pageTracked = true;
    const ref = document.referrer && new URL(document.referrer).host !== location.host ? document.referrer : undefined;
    track("page_view", { ref, utm: utm() });
    const product = document.querySelector("#product_details[data-vela-sku]");
    if (product?.dataset.velaSku) {
        track("product_view", { product: product.dataset.velaSku });
    }
    if (CHECKOUT_PATHS.includes(location.pathname)) {
        const key = `vela_checkout_started:${cookie.get(SESSION_COOKIE) || "new"}`;
        try {
            if (!sessionStorage.getItem(key)) {
                sessionStorage.setItem(key, "1");
                track("checkout_started");
            }
        } catch {
            track("checkout_started");
        }
    }
}

let pageTracked = false; // page-level events once per load, even if the interaction restarts

export class VelaAnalyticsTracker extends Interaction {
    static selector = "#wrapwrap";

    start() {
        start(this);
    }
}

registry.category("public.interactions").add("vela_analytics.tracker", VelaAnalyticsTracker);
