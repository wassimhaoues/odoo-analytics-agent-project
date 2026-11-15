#!/usr/bin/env node
// Scroll-performance probe for the homepage (or any path): scrolls continuously through the
// page like a user and reports frame timing + main-thread work (Chrome DevTools Protocol).
//
//   node scripts/scroll_perf.mjs [path] [--runs 3]
//
// Output per run: frames, median/p95 frame time, % of frames over 33 ms (visible jank),
// main-thread style/layout/script time, and paint/raster/composite cost from a trace.
// Headless Chrome renders in software, so absolute numbers are pessimistic. Compare runs.
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const args = process.argv.slice(2);
const target = args.find((a) => a.startsWith("/")) || "/";
const runs = Number(args[args.indexOf("--runs") + 1]) || (args.includes("--runs") ? 3 : 2);
const CHROME = [process.env.CHROME_BIN, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"]
    .find((c) => c && path.isAbsolute(c) && fs.existsSync(c));
const PORT = 9400 + Math.floor(Math.random() * 400);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "vela-perf-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let tabs;
for (let i = 0; i < 60; i++) {
    try { tabs = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); if (tabs.find((t) => t.type === "page")) break; } catch { /* starting */ }
    await sleep(250);
}
const ws = new WebSocket(tabs.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let seq = 0;
const pending = {};
let traceEvents = [];
let traceDone = null;
ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; }
    if (m.method === "Tracing.dataCollected") traceEvents.push(...m.params.value);
    if (m.method === "Tracing.tracingComplete" && traceDone) traceDone();
};
const send = (method, params = {}) => new Promise((r) => { const i = ++seq; pending[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (x) => (await send("Runtime.evaluate", { expression: x, returnByValue: true, awaitPromise: true })).result.result.value;
const metrics = async () => Object.fromEntries((await send("Performance.getMetrics")).result.metrics.map((m) => [m.name, m.value]));

await send("Performance.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
for (let run = 1; run <= runs; run++) {
    await send("Page.navigate", { url: `http://127.0.0.1:8069${target}` });
    await sleep(5000);
    traceEvents = [];
    await send("Tracing.start", { categories: "devtools.timeline,disabled-by-default-devtools.timeline,cc,gpu", transferMode: "ReportEvents" });
    const before = await metrics();
    // ~4 s of continuous wheel scrolling (goes through Lenis like a real user)
    const result = await ev(`new Promise((resolve) => {
        const times = []; let last = performance.now(); let n = 0;
        const step = () => {
            const now = performance.now(); times.push(now - last); last = now;
            window.dispatchEvent(new WheelEvent('wheel', { deltaY: 24, bubbles: true, cancelable: true }));
            if (!window.Lenis) window.scrollBy(0, 24);
            if (++n < 240) requestAnimationFrame(step); else resolve(times.slice(5));
        };
        requestAnimationFrame(step);
    })`);
    const after = await metrics();
    const done = new Promise((r) => (traceDone = r));
    await send("Tracing.end");
    await done;
    const sum = (names) => (traceEvents.filter((t) => names.includes(t.name) && t.dur).reduce((a, t) => a + t.dur, 0) / 1000).toFixed(0);
    const count = (names) => traceEvents.filter((t) => names.includes(t.name)).length;
    const sorted = [...result].sort((a, b) => a - b);
    const pct = (p) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))].toFixed(1);
    const d = (k) => ((after[k] - before[k]) * 1000).toFixed(0);
    console.log(JSON.stringify({
        run, frames: result.length, medianMs: pct(0.5), p95Ms: pct(0.95),
        jankPct: ((result.filter((t) => t > 33.4).length / result.length) * 100).toFixed(1),
        mainThreadMs: { style: d("RecalcStyleDuration"), layout: d("LayoutDuration"), script: d("ScriptDuration"), task: d("TaskDuration") },
        paintMs: sum(["Paint", "PaintImage"]), paints: count(["Paint"]),
        rasterMs: sum(["RasterTask", "RasterDecoderImpl::DoEndRasterCHROMIUM", "GPUTask"]),
        compositeMs: sum(["CompositeLayers", "UpdateLayerTree", "Layerize", "PrePaint"]),
        scrolledTo: await ev("Math.round(scrollY)"),
    }));
}
ws.close();
chrome.kill();
await new Promise((r) => chrome.once("exit", r));
try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* best effort */ }
