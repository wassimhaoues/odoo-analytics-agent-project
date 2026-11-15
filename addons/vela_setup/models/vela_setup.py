import base64
import logging

from odoo import api, models
from odoo.tools.misc import file_open

_logger = logging.getLogger(__name__)

# Shared store settings. Change them HERE, not in the Odoo UI.
COMPANY = {
    "name": "Vela Tech",
    # Neutral placeholders: real personal contact data never goes in git.
    "email": "hello@vela-tech.example",
    "website": "http://localhost:8069",
    "city": "Tunis",
}
TIMEZONE = "Africa/Tunis"
# Catalog prices are Tunisian retail prices, VAT (19%) already included.
PRICE_INCLUDE = "tax_included"
WEBSITE_NAME = "Vela Tech"
LANGUAGES = ["en_US", "fr_FR"]          # first = website default
DEMO_PAYMENT = {"active": True, "is_live": False, "is_published": True}  # test mode
LOGO = "vela_theme/static/src/img/logo.svg"
# Main menu, in order. Categories are matched by name in product.public.category.
MENU = ["Electronics", "Audio", "Computer Accessories", "Gaming", "Smart Home", "Bags & Cases"]
MENU_LABELS = {"Computer Accessories": "Accessories"}
MENU_DROP_URLS = {"/", "/blog", "/contactus", "/shop"}   # defaults replaced by the category menu
HEADER_VIEWS_OFF = ["website.header_call_to_action", "website.header_text_element"]
VIEWS_ON = ["website_sale.filter_products_price"]          # price range filter in the shop
# Shop grid + product page layout (website fields; see website_sale/models/website.py)
SHOP = {
    "shop_ppg": 24,
    "shop_ppr": 4,
    "shop_gap": "24px",
    "shop_opt_products_design_classes": " ".join([
        "o_wsale_products_opt_layout_catalog", "o_wsale_products_opt_design_thumbs",
        "o_wsale_products_opt_name_color_regular", "o_wsale_products_opt_rounded_3",
        "o_wsale_products_opt_thumb_cover", "o_wsale_products_opt_img_secondary_show",
        "o_wsale_products_opt_img_hover_zoom_in_light", "o_wsale_products_opt_has_cta",
        "o_wsale_products_opt_actions_onhover", "o_wsale_products_opt_has_wishlist",
        "o_wsale_products_opt_wishlist_fixed_onhover", "o_wsale_products_opt_has_comparison",
        "o_wsale_products_opt_actions_subtle", "o_wsale_products_opt_cc1",
    ]),
    "product_page_image_layout": "carousel",
    "product_page_image_width": "50_pc",
    "product_page_image_ratio": "1_1",
    "product_page_image_roundness": "medium",
    "product_page_image_spacing": "small",
}
# Shop filters: only what buyers actually filter by (progressive disclosure).
# Every other spec attribute stays on the product page spec table.
FILTER_ATTRIBUTES = ["Brand", "Color", "Storage", "Memory", "Size", "Capacity", "Switch Type",
                     "Screen Size", "Operating System", "Connectivity"]
# Ribbon look (records come from vela_tech_catalog): badges, palette colours.
RIBBONS = {
    "Sale":         {"style": "tag", "bg_color": "#C21E6B", "text_color": "#FFFFFF"},
    "Best Seller":  {"style": "tag", "bg_color": "#14213D", "text_color": "#FFFFFF"},
    "New":          {"style": "tag", "bg_color": "#0F5FB0", "text_color": "#FFFFFF"},
    "Limited":      {"style": "tag", "bg_color": "#E9ECE8", "text_color": "#14213D"},
    "Out of Stock": {"style": "tag", "bg_color": "#4E5A70", "text_color": "#FFFFFF"},
}


class VelaSetup(models.AbstractModel):
    _name = "vela.setup"
    _description = "Vela Tech reproducible store settings"

    @api.model
    def apply(self):
        """Idempotent. Runs on every install/upgrade of vela_setup (data/setup.xml)."""
        self._apply_languages()
        self._apply_company()
        self._apply_website()
        self._apply_payments()
        _logger.info("vela_setup: store settings applied")
        return True

    def _apply_languages(self):
        Lang = self.env["res.lang"]
        for code in LANGUAGES:
            if not Lang.search([("code", "=", code)]):
                Lang._activate_and_install_lang(code)

    def _apply_company(self):
        company = self.env.ref("base.main_company")
        vals = {"name": COMPANY["name"], "account_price_include": PRICE_INCLUDE}
        # contact fields only fill blanks, so a developer's local real data is kept
        for field in ("email", "website", "city"):
            if not company[field]:
                vals[field] = COMPANY[field]
        company.write(vals)
        self.env.ref("base.user_admin").tz = TIMEZONE

    def _apply_website(self):
        langs = self.env["res.lang"].search([("code", "in", LANGUAGES)])
        default = langs.filtered(lambda lang: lang.code == LANGUAGES[0])
        with file_open(LOGO, "rb") as f:
            logo = base64.b64encode(f.read()).decode()
        for website in self.env["website"].search([]):
            website.write({
                "name": WEBSITE_NAME,
                "language_ids": [(6, 0, langs.ids)],
                "default_lang_id": default.id,
                "logo": logo,
            })
            self._apply_menu(website)
            utils = self.env["theme.utils"].with_context(website_id=website.id)
            for xmlid in HEADER_VIEWS_OFF:
                utils.disable_view(xmlid)
            for xmlid in VIEWS_ON:
                utils.enable_view(xmlid)
            website.write(SHOP)
        self._apply_shop_catalog()

    def _apply_shop_catalog(self):
        Attr = self.env["product.attribute"]
        for attr in Attr.search([]):
            vis = "visible" if attr.name in FILTER_ATTRIBUTES else "hidden"
            if attr.visibility != vis:
                attr.visibility = vis
        for ribbon in self.env["product.ribbon"].search([("name", "in", list(RIBBONS))]):
            ribbon.write(RIBBONS[ribbon.name])

    def _apply_menu(self, website):
        top = website.menu_id
        if not top:
            return
        Categ = self.env["product.public.category"]
        slug = self.env["ir.http"]._slug
        top.child_id.filtered(lambda m: m.url in MENU_DROP_URLS).unlink()
        for seq, name in enumerate(MENU, start=1):
            categ = Categ.search([("name", "=", name), ("parent_id", "=", False)], limit=1)
            if not categ:
                continue
            url = f"/shop/category/{slug(categ)}"
            label = MENU_LABELS.get(name, name)
            menu = top.child_id.filtered(lambda m, u=url: m.url == u)[:1]
            vals = {"name": label, "url": url, "sequence": seq * 10,
                    "parent_id": top.id, "website_id": website.id}
            if menu:
                menu.write(vals)
            else:
                self.env["website.menu"].create(vals)

    def _apply_payments(self):
        demo = self.env["payment.provider"].with_context(active_test=False).search(
            [("code", "=", "demo")])
        demo.write(DEMO_PAYMENT)
