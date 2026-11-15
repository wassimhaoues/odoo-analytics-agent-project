#!/usr/bin/env python3
"""Find, review and fetch freely-licensed product images for the Vela Tech catalog.

Sources: Wikimedia Commons (primary) and Openverse (fallback). Only licenses that allow
reuse and modification are kept (CC0, Public Domain, CC BY, CC BY-SA).

Usage:
  # 1) search candidates for several products, build one contact sheet to review
  images.py search --sheet /tmp/laptops.png \
      VT-LAP-001="MacBook Air M2" VT-LAP-002="Dell XPS 13|Dell XPS 13 9310"
      (use | to try several queries; prefix a query with ov: to search Openverse only)

  # 2) fetch the chosen candidate(s) -> square white-background JPEG + credits json
  images.py pick VT-LAP-001 3 5        # candidate #3 = main image, #5 = extra gallery image

  # 3) direct file when the search missed it
  images.py pick VT-LAP-001 --commons "File:Some photo.jpg"

Candidates are cached in scripts/catalog/.cache/<sku>.json between search and pick.
"""
import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons" / "vela_tech_catalog"
IMG_DIR = ADDON / "static" / "img" / "products"
CREDITS_DIR = ADDON / "data" / "image_credits"
CACHE = Path(__file__).resolve().parent / ".cache"

UA = {"User-Agent": "vela-tech-study-catalog/0.1 (educational project; python-requests)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"
OK_LICENSE = re.compile(r"^(cc0|cc[- ]by(-sa)?( \d\.\d)?.*|public domain|pdm|no restrictions|by|by-sa)$", re.I)
FINAL_SIZE = 1200
PER_QUERY = 8

session = requests.Session()
session.headers.update(UA)


def _get(url, **kw):
    for attempt in range(8):
        try:
            r = session.get(url, timeout=(10, 30), **kw)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(5 + attempt * 5)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = r.headers.get("Retry-After", "")
            wait = int(retry_after) if retry_after.isdigit() else 5 + attempt * 5
            time.sleep(min(wait, 60))
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search_commons(query, limit=PER_QUERY):
    data = _get(COMMONS, params=dict(
        action="query", format="json", generator="search", gsrsearch=f"{query} filetype:bitmap",
        gsrnamespace=6, gsrlimit=limit, prop="imageinfo", iiprop="url|size|extmetadata",
        iiurlwidth=1280, iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")).json()
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p["index"])
    out = []
    for p in pages:
        ii = p["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not OK_LICENSE.match(lic.strip()) or min(ii["width"], ii["height"]) < 400:
            continue
        out.append(dict(
            source="commons", title=p["title"], page=ii["descriptionurl"],
            url=ii.get("thumburl") or ii["url"], width=ii["width"], height=ii["height"],
            license=lic, license_url=meta.get("LicenseUrl", {}).get("value", ""),
            author=strip_html(meta.get("Artist", {}).get("value", "")) or "Unknown",
        ))
    return out


def search_openverse(query, limit=PER_QUERY):
    data = _get(OPENVERSE, params=dict(q=query, page_size=limit, license="cc0,pdm,by,by-sa",
                                       mature="false")).json()
    out = []
    for it in data.get("results", []):
        w, h = it.get("width") or 0, it.get("height") or 0
        if w and h and min(w, h) < 400:
            continue
        lic = f"CC {it['license'].upper()} {it.get('license_version') or ''}".strip()
        if it["license"] in ("cc0", "pdm"):
            lic = it["license"].upper()
        out.append(dict(
            source="openverse", title=it.get("title") or it["id"], page=it.get("foreign_landing_url"),
            url=it["url"], width=w, height=h, license=lic, license_url=it.get("license_url", ""),
            author=it.get("creator") or "Unknown",
        ))
    return out


def run_queries(spec):
    cands, seen = [], set()
    for q in [q.strip() for q in spec.split("|") if q.strip()]:
        if q.startswith("ov:"):
            res = search_openverse(q[3:])
        else:
            res = search_commons(q)
        for c in res:
            if c["url"] not in seen:
                seen.add(c["url"])
                cands.append(c)
    return cands


def small_url(url):
    """Commons serves pre-rendered standard widths; 330px is cheap and rarely throttled."""
    return re.sub(r"/1280px-", "/330px-", url) if "/thumb/" in url else url


def thumb(url, size=220):
    url = small_url(url)
    try:
        img = Image.open(io.BytesIO(_get(url).content))
        img = flatten(img)
        img.thumbnail((size, size))
        return img
    except Exception as e:  # noqa: BLE001 - report and keep going
        print(f"   thumb failed {url}: {e}", file=sys.stderr)
        return None


def flatten(img):
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def contact_sheet(rows, path, cell=220, max_cols=10):
    font = ImageFont.load_default()
    label_h, head_h = 18, 22
    cols = min(max_cols, max((len(c) for _, c in rows), default=1)) or 1
    W = cols * (cell + 6) + 6
    H = sum(head_h + label_h + cell + 8 for _ in rows) + 6
    sheet = Image.new("RGB", (W, H), "#dddddd")
    d = ImageDraw.Draw(sheet)
    y = 4
    for title, thumbs in rows:
        d.text((6, y + 4), title, fill="black", font=font)
        y += head_h
        for i, t in enumerate(thumbs[:cols]):
            x = 6 + i * (cell + 6)
            d.rectangle([x, y, x + cell, y + cell + label_h], fill="white")
            d.text((x + 4, y + 2), f"#{i + 1}", fill="red", font=font)
            if t is not None:
                sheet.paste(t, (x + (cell - t.width) // 2, y + label_h + (cell - t.height) // 2))
        y += label_h + cell + 8
    sheet.save(path)


def cmd_search(args):
    CACHE.mkdir(exist_ok=True)
    rows = []
    for item in args.items:
        sku, _, spec = item.partition("=")
        cands = run_queries(spec)
        (CACHE / f"{sku}.json").write_text(json.dumps(cands, indent=1))
        print(f"## {sku}  ({spec})  -> {len(cands)} candidates")
        for i, c in enumerate(cands, 1):
            print(f"   #{i:<2} [{c['source'][:2]}] {c['title'][:80]}  {c['width']}x{c['height']}  {c['license']}")
        rows.append((f"{sku}  {spec[:90]}", [thumb(c["url"]) for c in cands[:args.cols]]))
    if args.sheet:
        contact_sheet(rows, args.sheet, max_cols=args.cols)
        print(f"sheet: {args.sheet}")


def process(img):
    """Fit into a white square canvas with a small margin (uniform shop grid)."""
    img = flatten(img)
    inner = int(FINAL_SIZE * 0.94)
    img.thumbnail((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGB", (FINAL_SIZE, FINAL_SIZE), "white")
    canvas.paste(img, ((FINAL_SIZE - img.width) // 2, (FINAL_SIZE - img.height) // 2))
    return canvas


def commons_file(title):
    data = _get(COMMONS, params=dict(
        action="query", format="json", titles=title, prop="imageinfo", iiprop="url|size|extmetadata",
        iiurlwidth=1280, iiextmetadatafilter="LicenseShortName|Artist|LicenseUrl")).json()
    p = next(iter(data["query"]["pages"].values()))
    ii = p["imageinfo"][0]
    meta = ii.get("extmetadata", {})
    return dict(source="commons", title=p["title"], page=ii["descriptionurl"],
                url=ii.get("thumburl") or ii["url"], width=ii["width"], height=ii["height"],
                license=meta.get("LicenseShortName", {}).get("value", ""),
                license_url=meta.get("LicenseUrl", {}).get("value", ""),
                author=strip_html(meta.get("Artist", {}).get("value", "")) or "Unknown")


def cmd_pick(args):
    chosen = []
    if args.commons:
        chosen = [commons_file(t) for t in args.commons]
    else:
        cands = json.loads((CACHE / f"{args.sku}.json").read_text())
        chosen = [cands[n - 1] for n in args.numbers]
    if not chosen:
        sys.exit("nothing picked")
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    CREDITS_DIR.mkdir(parents=True, exist_ok=True)
    for old in IMG_DIR.glob(f"{args.sku}*.jpg"):
        old.unlink()
    credits = []
    for i, c in enumerate(chosen):
        name = f"{args.sku}.jpg" if i == 0 else f"{args.sku}_{i}.jpg"
        img = process(Image.open(io.BytesIO(_get(c["url"]).content)))
        img.save(IMG_DIR / name, "JPEG", quality=86, optimize=True, progressive=True)
        credits.append(dict(file=name, title=c["title"], page=c["page"], author=c["author"],
                            license=c["license"], license_url=c["license_url"], source=c["source"]))
        print(f"saved {name}  <- {c['title']} ({c['license']}, {c['author'][:40]})")
    (CREDITS_DIR / f"{args.sku}.json").write_text(json.dumps(credits, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("items", nargs="+", help='SKU="query|query2|ov:openverse query"')
    s.add_argument("--sheet", help="write a contact sheet PNG")
    s.add_argument("--cols", type=int, default=8)
    s.set_defaults(func=cmd_search)
    p = sub.add_parser("pick")
    p.add_argument("sku")
    p.add_argument("numbers", nargs="*", type=int, help="candidate numbers; first = main image")
    p.add_argument("--commons", nargs="+", help='exact Commons file titles ("File:...")')
    p.set_defaults(func=cmd_pick)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
