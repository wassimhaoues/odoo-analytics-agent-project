#!/usr/bin/env python3
"""Validate addons/vela_tech_catalog/data/catalog/*.json against SCHEMA.md rules.

Usage: scripts/catalog/validate.py [file.json ...]   (default: all category files)
Exit code 1 on errors; warnings are printed but do not fail.
"""
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons" / "vela_tech_catalog"
DATA = ADDON / "data" / "catalog"
IMG = ADDON / "static" / "img" / "products"
CREDITS = ADDON / "data" / "image_credits"
SKIP = {"_meta.json", "crosssell.json"}

meta = json.loads((DATA / "_meta.json").read_text())
files = [Path(a) for a in sys.argv[1:]] or sorted(p for p in DATA.glob("*.json") if p.name not in SKIP)
errors, warnings = [], []
all_skus = {}


def err(where, msg):
    errors.append(f"{where}: {msg}")


def warn(where, msg):
    warnings.append(f"{where}: {msg}")


def in_stock(stock):
    return any(v > 0 for v in stock.values()) if isinstance(stock, dict) else stock > 0


for path in files:
    data = json.loads(path.read_text())
    fname = path.name
    vendors = data.get("vendors", {})
    specs_ok = set(meta["spec_attributes"]) | set(data.get("extra_specs", {}))
    colors_ok = set(meta["colors"]) | set(data.get("colors", {}))
    for sub in data["subcategories"]:
        sname = sub["name"]
        if sname not in meta["sku_prefix"]:
            err(fname, f"unknown subcategory {sname!r}")
            continue
        prods = sub["products"]
        if not 5 <= len(prods) <= 10:
            warn(sname, f"{len(prods)} products (expected 5-10)")
        stocks = [p.get("stock", 0) for p in prods]
        if not any(not in_stock(s) for s in stocks):
            warn(sname, "no out-of-stock product")
        if not any(p.get("compare_list_price") for p in prods):
            warn(sname, "no product on sale")
        for p in prods:
            sku = p.get("sku", "?")
            w = f"{fname}:{sku}"
            if sku in all_skus:
                err(w, f"duplicate SKU (also in {all_skus[sku]})")
            all_skus[sku] = fname
            if not sku.startswith(f"VT-{meta['sku_prefix'][sname]}-"):
                err(w, f"SKU prefix should be VT-{meta['sku_prefix'][sname]}-")
            for k in ("name", "brand", "vendor", "list_price", "cost", "short", "description"):
                if not p.get(k):
                    err(w, f"missing {k}")
            if p.get("vendor") not in vendors:
                err(w, f"vendor {p.get('vendor')!r} not in file vendors")
            if p.get("cost", 0) >= p.get("list_price", 0):
                err(w, "cost >= list_price")
            if p.get("compare_list_price") and p["compare_list_price"] <= p["list_price"]:
                err(w, "compare_list_price must be > list_price")
            for s in p.get("specs", {}):
                if s not in specs_ok:
                    err(w, f"unknown spec {s!r} (add to extra_specs)")
            vdefs = p.get("variants", [])
            combos = 1
            for v in vdefs:
                if v["attribute"] not in meta["variant_attributes"]:
                    err(w, f"unknown variant attribute {v['attribute']!r}")
                if v["attribute"] in specs_ok:
                    err(w, f"{v['attribute']!r} is both spec and variant")
                if v["attribute"] == "Color":
                    for n, _ in v["values"]:
                        if n not in colors_ok:
                            err(w, f"color {n!r} has no hex (add to file colors)")
                combos *= len(v["values"])
            if combos > 12:
                err(w, f"{combos} variants (max 12)")
            keys = {" / ".join(c) for c in itertools.product(*[[n for n, _ in v["values"]] for v in vdefs])}
            st = p.get("stock", 0)
            if isinstance(st, dict):
                for k in st:
                    if k != "*" and k not in keys:
                        err(w, f"stock key {k!r} matches no variant")
            for t in p.get("tags", []):
                if t not in meta["tags"]:
                    err(w, f"unknown tag {t!r}")
            if p.get("ribbon") and p["ribbon"] not in meta["ribbons"]:
                err(w, f"unknown ribbon {p['ribbon']!r}")
            if not (IMG / f"{sku}.jpg").exists():
                err(w, "missing main image")
            if not (CREDITS / f"{sku}.json").exists():
                err(w, "missing image credits")

for path in files:
    for sub in json.loads(path.read_text())["subcategories"]:
        for p in sub["products"]:
            for a in p.get("alternatives", []):
                if a not in all_skus:
                    err(f"{path.name}:{p['sku']}", f"alternative {a} not found")

print(f"{len(all_skus)} products checked in {len(files)} files")
for w in warnings:
    print("WARN ", w)
for e in errors:
    print("ERROR", e)
sys.exit(1 if errors else 0)
