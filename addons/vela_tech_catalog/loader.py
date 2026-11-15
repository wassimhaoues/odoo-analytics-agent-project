"""Load the Vela Tech catalog from data/catalog/*.json into Odoo.

Idempotent: every record created here gets an xmlid in this module (noupdate), and existing
records are reused instead of duplicated. Re-run from an Odoo shell with:

    from odoo.addons.vela_tech_catalog.loader import load_catalog; load_catalog(env); env.cr.commit()
"""
import base64
import json
import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

MODULE = "vela_tech_catalog"
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "catalog"
IMG = ROOT / "static" / "img" / "products"
NOT_PRODUCT_FILES = {"_meta.json", "crosssell.json"}


# --------------------------------------------------------------------------- helpers
def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def ean13(n):
    """Valid EAN-13 in the Tunisian GS1 range (619) from a running number."""
    body = f"6199{n:08d}"
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


def read_image(name):
    path = IMG / name
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else False


class Loader:
    def __init__(self, env):
        self.env = env
        self.meta = json.loads((DATA / "_meta.json").read_text())
        self.files = [json.loads(p.read_text()) for p in sorted(DATA.glob("*.json"))
                      if p.name not in NOT_PRODUCT_FILES]
        self.attr_cache, self.value_cache = {}, {}
        self.barcode_seq = 0
        self.templates = {}       # sku -> product.template
        self.sku_info = {}        # sku -> (product dict, subcategory name)

    # ---- xmlid-backed get-or-create
    def _xmlid(self, name):
        return f"{MODULE}.{name}"

    def ensure(self, model, name, vals, update=False):
        rec = self.env.ref(self._xmlid(name), raise_if_not_found=False)
        if rec:
            if update:
                rec.write(vals)
            return rec, False
        rec = self.env[model].create(vals)
        self.env["ir.model.data"].create({
            "module": MODULE, "name": name, "model": model, "res_id": rec.id, "noupdate": True,
        })
        return rec, True

    # ------------------------------------------------------------------ setup
    def setup_company(self):
        company = self.env.company
        if company.name in ("My Company", "YourCompany"):
            company.name = self.meta["company"]["name"]
        for website in self.env["website"].search([]):
            if website.name in ("My Website", "My Company", "Website"):
                website.name = self.meta["company"]["website"]
        self.env["res.config.settings"].create({
            "group_product_variant": True,
            "group_product_price_comparison": True,
        }).execute()

    def setup_attributes(self):
        groups = {}
        for seq, g in enumerate(self.meta["spec_groups"]):
            groups[g], _ = self.ensure("product.attribute.category", f"attr_group_{slug(g)}",
                                       {"name": g, "sequence": seq})
        colors = dict(self.meta["colors"])
        specs = dict(self.meta["spec_attributes"])
        for f in self.files:
            colors.update({k: v for k, v in f.get("colors", {}).items() if k not in colors})
            specs.update({k: v for k, v in f.get("extra_specs", {}).items() if k not in specs})
        self.colors = colors
        for seq, (name, conf) in enumerate(self.meta["variant_attributes"].items()):
            vals = {"name": name, "create_variant": "always", "display_type": conf["display_type"],
                    "sequence": seq, "visibility": "visible",
                    "preview_variants": conf.get("preview_variants", "hidden")}
            self.attr_cache[name], _ = self.ensure("product.attribute", f"attr_{slug(name)}", vals)
        for seq, (name, group) in enumerate(specs.items(), start=100):
            vals = {"name": name, "create_variant": "no_variant", "display_type": "radio",
                    "sequence": seq, "visibility": "visible",
                    "category_id": groups.get(group, groups["General"]).id}
            self.attr_cache[name], _ = self.ensure("product.attribute", f"spec_{slug(name)}", vals)

    def value(self, attr_name, value_name):
        key = (attr_name, value_name)
        if key not in self.value_cache:
            attr = self.attr_cache[attr_name]
            vals = {"name": value_name, "attribute_id": attr.id}
            if attr.display_type == "color":
                vals["html_color"] = self.colors.get(value_name, "#999999")
            xid = f"val_{slug(attr_name)}_{slug(value_name)}"[:120]
            self.value_cache[key], _ = self.ensure("product.attribute.value", xid, vals)
        return self.value_cache[key]

    def setup_tags_ribbons(self):
        self.tags = {}
        for name, color in self.meta["tags"].items():
            self.tags[name], _ = self.ensure("product.tag", f"tag_{slug(name)}",
                                             {"name": name, "color": color, "visible_to_customers": True})
        self.ribbons = {}
        for seq, (name, conf) in enumerate(self.meta["ribbons"].items()):
            existing = self.env["product.ribbon"].search([("assign", "=", conf["assign"])], limit=1) \
                if conf["assign"] != "manual" else None
            if existing and not self.env.ref(self._xmlid(f"ribbon_{slug(name)}"), raise_if_not_found=False):
                existing.write({k: v for k, v in conf.items() if k != "assign"} | {"name": name})
                self.ribbons[name] = existing
                continue
            self.ribbons[name], _ = self.ensure("product.ribbon", f"ribbon_{slug(name)}",
                                                dict(conf, name=name, sequence=seq))

    def setup_vendors(self):
        self.vendors, self.lead_days = {}, {}
        merged = {}
        for f in self.files:
            for k, v in f.get("vendors", {}).items():
                merged.setdefault(k, v)
        for name, conf in merged.items():
            self.vendors[name], _ = self.ensure("res.partner", f"vendor_{slug(name)}", {
                "name": name, "is_company": True, "supplier_rank": 1,
                "comment": f"Supplier for {name} products (lead time {conf.get('lead_days', 7)} days).",
            })
            self.lead_days[name] = conf.get("lead_days", 7)

    def setup_categories(self):
        all_categ = self.env.ref("product.product_category_all", raise_if_not_found=False)
        saleable, _ = self.ensure("product.category", "categ_saleable",
                                  {"name": "Saleable", "parent_id": all_categ.id if all_categ else False})
        self.internal_categ, self.public_categ = {}, {}
        for seq, f in enumerate(self.files):
            top = f["category"]
            icat, _ = self.ensure("product.category", f"categ_{slug(top)}",
                                  {"name": top, "parent_id": saleable.id})
            pcat, _ = self.ensure("product.public.category", f"pcateg_{slug(top)}", {
                "name": top, "sequence": seq * 10,
                "website_description": f"<p>{f.get('description', '')}</p>",
            })
            for sseq, sub in enumerate(f["subcategories"]):
                self.internal_categ[sub["name"]] = icat
                self.public_categ[sub["name"]], _ = self.ensure(
                    "product.public.category", f"pcateg_{slug(top)}_{slug(sub['name'])}", {
                        "name": sub["name"], "parent_id": pcat.id, "sequence": sseq,
                        "website_description": f"<p>{sub.get('description', '')}</p>",
                    })
            self.public_categ[top] = pcat

    # ------------------------------------------------------------------ products
    def create_product(self, p, subcat, seq):
        xid = f"product_{slug(p['sku'])}"
        existing = self.env.ref(self._xmlid(xid), raise_if_not_found=False)
        if existing:
            return existing
        vendor = self.vendors[p["vendor"]]
        lead_days = self.lead_days[p["vendor"]]
        variant_defs = p.get("variants", [])
        lines = []
        for v in variant_defs:
            lines.append((0, 0, {"attribute_id": self.attr_cache[v["attribute"]].id,
                                 "value_ids": [(6, 0, [self.value(v["attribute"], n).id for n, _ in v["values"]])]}))
        specs = dict(p.get("specs", {}))
        specs.setdefault("Brand", p["brand"])
        for name, val in specs.items():
            if name not in self.attr_cache:
                _logger.warning("%s: unknown spec %r skipped", p["sku"], name)
                continue
            lines.append((0, 0, {"attribute_id": self.attr_cache[name].id,
                                 "value_ids": [(6, 0, [self.value(name, str(val)).id])]}))
        gallery = sorted(IMG.glob(f"{p['sku']}_*.jpg"))
        vals = {
            "name": p["name"],
            "type": "consu",
            "is_storable": True,
            "sale_ok": True,
            "purchase_ok": True,
            "list_price": p["list_price"],
            "standard_price": p["cost"],
            "categ_id": self.internal_categ[subcat].id,
            "public_categ_ids": [(6, 0, [self.public_categ[subcat].id])],
            "weight": p.get("weight", 0.0),
            "description_sale": p.get("short", ""),
            "description_ecommerce": p.get("description", ""),
            "product_tag_ids": [(6, 0, [self.tags[t].id for t in p.get("tags", []) if t in self.tags])],
            "website_ribbon_id": self.ribbons[p["ribbon"]].id if p.get("ribbon") in self.ribbons else False,
            "compare_list_price": p.get("compare_list_price") or 0.0,
            "is_published": True,
            "website_sequence": seq if p.get("featured") else 1000 + seq,
            "image_1920": read_image(f"{p['sku']}.jpg"),
            "allow_out_of_stock_order": False,
            "show_availability": True,
            "available_threshold": 5,
            "invoice_policy": "order",
            "attribute_line_ids": lines,
            "seller_ids": [(0, 0, {"partner_id": vendor.id, "price": p["cost"], "min_qty": 1,
                                   "delay": lead_days, "product_code": p["sku"],
                                   "product_name": p["name"]})],
            "product_template_image_ids": [(0, 0, {"name": f"{p['name']} ({i + 1})",
                                                   "image_1920": base64.b64encode(g.read_bytes()).decode()})
                                           for i, g in enumerate(gallery)],
        }
        if not variant_defs:
            vals["default_code"] = p["sku"]
        tmpl = self.env["product.template"].create(vals)
        self.env["ir.model.data"].create({"module": MODULE, "name": xid, "model": "product.template",
                                          "res_id": tmpl.id, "noupdate": True})
        self._setup_variants(tmpl, p, variant_defs)
        return tmpl

    def _setup_variants(self, tmpl, p, variant_defs):
        extras = {}
        for v in variant_defs:
            for name, extra in v["values"]:
                extras[(v["attribute"], name)] = extra
                if extra:
                    ptav = tmpl.attribute_line_ids.product_template_value_ids.filtered(
                        lambda x, a=v["attribute"], n=name: x.attribute_id.name == a and x.name == n)
                    ptav.price_extra = extra
        order = [v["attribute"] for v in variant_defs]
        stock = p.get("stock", 0)
        ratio = p["cost"] / p["list_price"] if p["list_price"] else 0.75
        variants = tmpl.product_variant_ids.sorted("id")
        for idx, variant in enumerate(variants, start=1):
            ptavs = {x.attribute_id.name: x.name for x in variant.product_template_attribute_value_ids}
            key = " / ".join(ptavs[a] for a in order if a in ptavs)
            extra = sum(extras.get((a, ptavs[a]), 0) for a in order if a in ptavs)
            self.barcode_seq += 1
            vvals = {"barcode": ean13(self.barcode_seq)}
            if variant_defs:
                vvals["default_code"] = f"{p['sku']}-{idx}"
                vvals["standard_price"] = round(p["cost"] + extra * ratio, 3)
            variant.write(vvals)
            qty = stock.get(key, stock.get("*", 0)) if isinstance(stock, dict) else stock
            if qty:
                self.env["stock.quant"].with_context(inventory_mode=True).create({
                    "product_id": variant.id, "location_id": self.stock_location.id,
                    "inventory_quantity": qty,
                }).action_apply_inventory()
            if p.get("reorder"):
                self.env["stock.warehouse.orderpoint"].create({
                    "product_id": variant.id, "warehouse_id": self.warehouse.id,
                    "location_id": self.stock_location.id,
                    "product_min_qty": p["reorder"]["min"], "product_max_qty": p["reorder"]["max"],
                    "trigger": "auto",
                })

    def load_products(self):
        self.warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        self.stock_location = self.warehouse.lot_stock_id
        # continue barcode numbering after any barcodes we already assigned
        used = self.env["product.product"].with_context(active_test=False).search(
            [("barcode", "=like", "6199%")]).mapped("barcode")
        self.barcode_seq = max((int(b[4:12]) for b in used), default=0)
        seq = 0
        for f in self.files:
            for sub in f["subcategories"]:
                for p in sub["products"]:
                    seq += 1
                    self.sku_info[p["sku"]] = (p, sub["name"])
                    self.templates[p["sku"]] = self.create_product(p, sub["name"], seq)
        # category cover images = first product with an image
        for name, pcat in self.public_categ.items():
            if not pcat.cover_image:
                tmpl = self.env["product.template"].search(
                    [("public_categ_ids", "child_of", pcat.id), ("image_1920", "!=", False)],
                    order="website_sequence", limit=1)
                if tmpl:
                    pcat.cover_image = tmpl.image_1920

    # ------------------------------------------------------------------ cross-selling
    def link_products(self):
        for sku, (p, _sub) in self.sku_info.items():
            alts = [self.templates[s].id for s in p.get("alternatives", []) if s in self.templates]
            if alts:
                self.templates[sku].alternative_product_ids = [(6, 0, alts)]
        rules_path = DATA / "crosssell.json"
        if not rules_path.exists():
            return
        rules = json.loads(rules_path.read_text())
        per = rules.get("per_target", 2)
        by_sub = {}
        for sku, (p, sub) in self.sku_info.items():
            by_sub.setdefault(sub, []).append((sku, p))

        def best(sub):
            def in_stock(p):
                s = p.get("stock", 0)
                return any(s.values()) if isinstance(s, dict) else s > 0
            items = [x for x in by_sub.get(sub, []) if in_stock(x[1])]
            items.sort(key=lambda x: (not x[1].get("featured"), x[1]["list_price"]))
            return [self.templates[s] for s, _ in items[:per]]

        for src_sub, targets in rules.get("accessories", {}).items():
            acc = [t.product_variant_id.id for sub in targets for t in best(sub)]
            for sku, _p in by_sub.get(src_sub, []):
                self.templates[sku].accessory_product_ids = [(6, 0, acc)]
        for src_sub, targets in rules.get("optional", {}).items():
            opt = [t.id for sub in targets for t in best(sub)]
            for sku, _p in by_sub.get(src_sub, []):
                self.templates[sku].optional_product_ids = [(6, 0, opt)]

    def run(self):
        _logger.info("Vela Tech catalog: loading %d category files", len(self.files))
        self.setup_company()
        self.setup_attributes()
        self.setup_tags_ribbons()
        self.setup_vendors()
        self.setup_categories()
        self.load_products()
        self.link_products()
        _logger.info("Vela Tech catalog: %d products ready", len(self.templates))


def load_catalog(env):
    Loader(env).run()
