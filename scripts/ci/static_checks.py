#!/usr/bin/env python3
"""Static checks that need no Odoo: run locally or in CI (lint job).

    python3 scripts/ci/static_checks.py

Checks: every XML well-formed, every JSON valid, every Python file compiles, every addon
manifest sane (version 20.0.x, LGPL-3, declared data/asset files exist), vela_setup depends
on every addon in addons/. Exit 1 on the first category with errors, listing them all.
"""
import ast
import json
import sys
import xml.dom.minidom
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = (".git", "node_modules", ".cache", "ui-ux-pro-max/data", "__pycache__")
errors: list[str] = []


def files(pattern):
    for p in ROOT.rglob(pattern):
        rel = p.relative_to(ROOT).as_posix()
        if not any(s in rel for s in SKIP):
            yield p, rel


for p, rel in files("*.xml"):
    try:
        xml.dom.minidom.parse(str(p))
    except Exception as e:  # noqa: BLE001 - report every bad file
        errors.append(f"XML  {rel}: {e}")

for p, rel in files("*.json"):
    try:
        json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        errors.append(f"JSON {rel}: {e}")

for p, rel in files("*.py"):
    try:
        compile(p.read_text(), rel, "exec")       # syntax only, writes nothing
    except SyntaxError as e:
        errors.append(f"PY   {rel}:{e.lineno}: {e.msg}")

addons = sorted(p.parent for p in (ROOT / "addons").glob("*/__manifest__.py"))
for addon in addons:
    rel = addon.relative_to(ROOT).as_posix()
    m = ast.literal_eval((addon / "__manifest__.py").read_text())
    if not str(m.get("version", "")).startswith("20.0."):
        errors.append(f"MANIFEST {rel}: version must start with 20.0. (got {m.get('version')})")
    if m.get("license") != "LGPL-3":
        errors.append(f"MANIFEST {rel}: license must be LGPL-3")
    for f in m.get("data", []):
        if not (addon / f).exists():
            errors.append(f"MANIFEST {rel}: data file missing: {f}")
    for bundle, paths in m.get("assets", {}).items():
        for f in paths:
            if isinstance(f, str) and not (ROOT / "addons" / f).exists():
                errors.append(f"MANIFEST {rel}: asset missing in {bundle}: {f}")

setup = ast.literal_eval((ROOT / "addons/vela_setup/__manifest__.py").read_text())
for addon in addons:
    if addon.name != "vela_setup" and addon.name not in setup["depends"]:
        errors.append(f"REPRO vela_setup/__manifest__.py must depend on {addon.name} (reproducibility rule)")

if errors:
    print("\n".join(errors))
    print(f"\n{len(errors)} static check error(s)")
    sys.exit(1)
print(f"static checks OK ({len(addons)} addons)")
