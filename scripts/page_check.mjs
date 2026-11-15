#!/usr/bin/env node
// Real-device page check over Chrome DevTools Protocol (no npm deps, Node 22+).
// Catches what plain `--window-size` screenshots miss: mobile emulation, horizontal
// overflow, JS console errors, untracked interactive elements.
//
//   node scripts/page_check.mjs <out-dir> [path ...]        default paths: / /shop
//   node scripts/page_check.mjs /tmp/check / --reduced-motion --dark
//   node scripts/page_check.mjs out / /shop --strict      # CI: exit 1 on any issue
//
// Per path and width (375 mobile, 768 mobile, 1440 desktop) it writes
// <slug>-<width>.png (full page) and prints a JSON line:
//   {path, width, scrollWidth, overflowX, jsErrors[], untracked[], ms}
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
const OUT = args.shift();
if (!OUT) {
    console.error("usage: page_check.mjs <out-dir> [paths...] [--reduced-motion] [--dark]");
    process.exit(2);
}
const flags = new Set(args.filter((a) => a.startsWith("--")));
const paths = args.filter((a) => !a.startsWith("--"));
if (!paths.length) paths.push("/", "/shop");
fs.mkdirSync(OUT, { recursive: true });

const BASE = process.env.VELA_BASE_URL || "http://127.0.0.1:8069";
const PORT = 9300 + Math.floor(Math.random() * 500);
// Chrome profile lives in the OS temp dir (not in the uploaded artifacts) and cleanup is
// best-effort: Chrome helper processes can still be writing to it right after kill().
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "vela-page-check-"));
// Absolute browser path (no PATH lookup): $CHROME_BIN or the standard install locations.
const CHROME = [process.env.CHROME_BIN, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
    "/opt/google/chrome/chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
    .find((c) => c && path.isAbsolute(c) && fs.existsSync(c));
if (!CHROME) {
    console.error("No Chrome/Chromium found: set CHROME_BIN to its absolute path.");
    process.exit(2);
}
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let tabs;
for (let i = 0; i < 60; i++) {
    try {
        tabs = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
        if (tabs.find((t) => t.type === "page")) break;
    } catch { /* chrome still starting */ }
    await sleep(250);
}
const ws = new WebSocket(tabs.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let seq = 0;
const pending = {};
const errors = [];
ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; }
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description?.split("\n")[0] || m.params.exceptionDetails.text);
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value ?? a.description).join(" ").slice(0, 200));
};
const send = (method, params = {}) => new Promise((r) => { const i = ++seq; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;

await send("Page.enable");
await send("Runtime.enable");
const media = [];
if (flags.has("--reduced-motion")) media.push({ name: "prefers-reduced-motion", value: "reduce" });
if (flags.has("--dark")) media.push({ name: "prefers-color-scheme", value: "dark" });
if (media.length) await send("Emulation.setEmulatedMedia", { features: media });

const probeFor = (deviceWidth) => `(() => {
  const sw = document.documentElement.scrollWidth;
  const sel = 'a[href], button, [role=button], input[type=submit]';
  const untracked = [...document.querySelectorAll(sel)].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && !el.closest('[data-track]') && !el.closest('.o_cookies_discrete, #website_cookies_bar, .o_frontend_to_backend_nav, .o_skip_to_content');
  }).slice(0, 15).map(el => (el.dataset.name || el.className || el.tagName).toString().slice(0, 40) + ' "' + (el.textContent || '').trim().slice(0, 20) + '"');
  const offenders = sw > ${deviceWidth} ? [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.right > ${deviceWidth} + 1 && ![...el.children].some(c => c.getBoundingClientRect().right > ${deviceWidth} + 1);
  }).slice(0, 6).map(el => (el.className || el.tagName).toString().slice(0, 50) + ' right=' + Math.round(el.getBoundingClientRect().right)) : [];
  const autoTracked = [...document.querySelectorAll('[data-track-auto]')].slice(0, 10).map(el => el.dataset.track + ' "' + (el.textContent || el.title || '').trim().slice(0, 20) + '"');
  return { scrollWidth: sw, overflowX: sw > ${deviceWidth}, offenders, untracked, autoTracked };
})()`;

const failures = [];
for (const p of paths) {
    for (const width of [375, 768, 1440]) {
        errors.length = 0;
        const mobile = width < 992;
        await send("Emulation.setDeviceMetricsOverride", { width, height: mobile ? 812 : 900, deviceScaleFactor: 1, mobile });
        const t0 = Date.now();
        await send("Page.navigate", { url: BASE + p });
        // Ready = document loaded AND our interactions ran (header controls annotated).
        // A fixed sleep was flaky on cold runners, where the first request compiles assets.
        for (let waited = 0; waited < 20000; waited += 250) {
            const ready = await evaluate(`document.readyState === "complete" && (!document.querySelector("header#top")
                || !!document.querySelector("header#top .o_wsale_my_cart a[data-track], header#top [data-track='header.menu.open']"))`);
            if (ready) break;
            await sleep(250);
        }
        await sleep(1200);   // let dynamic snippets / late dialogs settle
        const probe = await evaluate(probeFor(width));
        const height = await evaluate("Math.min(document.documentElement.scrollHeight, 8000)");
        await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile });
        await sleep(600);
        const shot = await send("Page.captureScreenshot", { format: "png" });
        const slug = p.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "home";
        fs.writeFileSync(path.join(OUT, `${slug}-${width}.png`), Buffer.from(shot.result.data, "base64"));
        const result = { path: p, width, ...probe, jsErrors: [...new Set(errors)], ms: Date.now() - t0 };
        console.log(JSON.stringify(result));
        const problems = [
            result.overflowX && `horizontal overflow (${result.scrollWidth}px)`,
            result.jsErrors.length && `JS errors: ${result.jsErrors.join(" | ")}`,
            result.untracked.length && `untracked: ${result.untracked.join(", ")}`,
            result.autoTracked?.length && `auto-tracked (name them): ${result.autoTracked.join(", ")}`,
        ].filter(Boolean);
        if (problems.length) failures.push(`${p} @${width}: ${problems.join("; ")}`);
    }
}
ws.close();
chrome.kill();
await new Promise((r) => chrome.once("exit", r));
try {
    fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
} catch { /* leftover temp profile is harmless */ }
if (failures.length) {
    console.error(`\n${failures.length} page check failure(s):\n- ` + failures.join("\n- "));
    if (flags.has("--strict")) process.exit(1);
} else {
    console.error("page_check: all clean");
}
