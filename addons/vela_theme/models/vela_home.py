from odoo import api, models

HERO_SKU = "VT-CTL-001"          # DualSense: the cleanest cut-out photo in the catalog
COMPARE_SKUS = ["VT-HPH-001", "VT-HPH-008"]
COMPARE_SPECS = ["Battery Life"]


class VelaHome(models.AbstractModel):
    """Read-only data for the homepage sections (views/home.xml). Called with sudo()
    from QWeb; returns published records only."""
    _name = "vela.home"
    _description = "Vela Tech homepage data"

    def _published(self):
        return [("is_published", "=", True), ("sale_ok", "=", True)]

    def _by_sku(self, sku):
        return self.env["product.product"].search(
            [("default_code", "=like", f"{sku}%")], limit=1).product_tmpl_id

    def _specs(self, tmpl, names):
        lines = tmpl.attribute_line_ids.filtered(lambda l: l.attribute_id.name in names)
        # short form for tiles: "Up to 30 h (ANC on)" -> "Up to 30 h"
        return {l.attribute_id.name: (l.value_ids[:1].name or "").split("(")[0].strip() for l in lines}

    @api.model
    def _home_values(self):
        Tmpl = self.env["product.template"]
        published = Tmpl.search(self._published())
        top_categs = self.env["product.public.category"].search(
            [("parent_id", "=", False)], order="sequence, id")

        brand_lines = self.env["product.template.attribute.line"].search([
            ("attribute_id.name", "=", "Brand"), ("product_tmpl_id", "in", published.ids)])
        brand_count = {}
        for line in brand_lines:
            for v in line.value_ids:
                brand_count[v.name] = brand_count.get(v.name, 0) + 1
        brands = sorted(brand_count, key=lambda b: (-brand_count[b], b))

        deals = Tmpl.search(self._published() + [("compare_list_price", ">", 0)],
                            order="website_sequence, id", limit=16)
        deals = deals.filtered(lambda t: t.compare_list_price > t.list_price)[:8]

        sold_out = published.filtered(
            lambda t: t.is_storable and t.website_ribbon_id.name == "Best Seller" and t.qty_available <= 0)
        spotlight = sold_out[:1]
        waiting = self.env["product.stock.notification"].search_count(
            [("product_id.product_tmpl_id", "=", spotlight.id)]) if spotlight else 0

        hero = self._by_sku(HERO_SKU) or published[:1]
        compare = [(t, self._specs(t, COMPARE_SPECS)) for t in map(self._by_sku, COMPARE_SKUS) if t]

        return {
            "hero": hero,
            "product_count": len(published),
            "brand_count": len(brands),
            "brands": brands[:14],
            "categories": [(c, Tmpl.search_count(self._published() + [("public_categ_ids", "child_of", c.id)]))
                           for c in top_categs],
            "deals": [(t, round((t.compare_list_price - t.list_price) / t.compare_list_price * 100),
                       self._specs(t, ["Brand"]).get("Brand", "")) for t in deals],
            "spotlight": spotlight,
            "waiting": waiting,
            "compare": compare,
            "compare_specs": COMPARE_SPECS,
        }
