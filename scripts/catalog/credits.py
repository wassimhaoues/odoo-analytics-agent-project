#!/usr/bin/env python3
"""Build addons/vela_tech_catalog/IMAGE_CREDITS.md from data/image_credits/*.json."""
import json
from pathlib import Path

ADDON = Path(__file__).resolve().parents[2] / "addons" / "vela_tech_catalog"
rows = []
for f in sorted((ADDON / "data" / "image_credits").glob("*.json")):
    for c in json.loads(f.read_text()):
        author = c["author"].replace("|", "/").replace("\n", " ").strip()
        lic = f"[{c['license']}]({c['license_url']})" if c.get("license_url") else c["license"]
        rows.append(f"| `{c['file']}` | [{c['title'].removeprefix('File:')}]({c['page']}) | {author} | {lic} |")

out = ADDON / "IMAGE_CREDITS.md"
out.write_text(
    "# Image credits\n\n"
    "Product photos come from Wikimedia Commons and Openverse under free licenses. They were\n"
    "resized and padded onto a white square canvas (that is a modification). Product names and\n"
    "trademarks belong to their owners; this is a non-commercial study project.\n\n"
    "| File | Source | Author | License |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
print(f"{len(rows)} images credited -> {out}")
