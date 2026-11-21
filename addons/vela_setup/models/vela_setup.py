import base64
import json
import logging

from odoo import api, models
from odoo.tools.misc import file_open

_logger = logging.getLogger(__name__)

# Shared store settings. Change them HERE, not in the Odoo UI.
STORE_NAME = "Vela Tech"
COMPANY = {
    "name": STORE_NAME,
    # Neutral placeholders: real personal contact data never goes in git.
    "email": "hello@vela-tech.example",
    "website": "http://localhost:8069",
    "street": "Avenue Habib Bourguiba",
    "zip": "1000",
    "city": "Tunis",
    "phone": "+216 70 000 000",
}
WAREHOUSE_NAME = STORE_NAME
# Tunisian VAT, applied to every product we sell. Prices in the catalog already include it.
SALE_TAX_PERCENT = 19.0
TIMEZONE = "Africa/Tunis"
# Catalog prices are Tunisian retail prices, VAT (19%) already included.
PRICE_INCLUDE = "tax_included"
WEBSITE_NAME = STORE_NAME
LANGUAGES = ["en_US", "fr_FR"]          # first = website default
# No online payment (ADR 0009): customers pay cash when the order arrives, or at pickup.
PAY_ON_DELIVERY = ["cash_on_delivery", "on_site"]        # payment.provider custom_mode; all others off
PAYMENT_TEXT = {
    "cash_on_delivery": ("Cash on delivery", "Paiement à la livraison",
                         "Pay in cash when your order arrives. No card needed.",
                         "Payez en espèces à la réception de votre commande. Aucune carte nécessaire."),
    "on_site": ("Pay at pickup", "Paiement au retrait",
                "Pay in our Tunis store when you collect your order.",
                "Payez dans notre magasin de Tunis au retrait de votre commande."),
}
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
    # Customer accounts: anyone can sign up (b2c); at checkout an account is optional (guest OK)
    "auth_signup_uninvited": "b2c",
    "account_on_checkout": "optional",
    # catalog prices are shown VAT included, as Tunisian law requires for consumers
    "show_line_subtotals_tax_selection": "tax_included",
    # consent before optional (analytics) cookies: spec FR-01 / T2
    "cookies_bar": True,
}
COOKIE_POLICY_PAGE = "vela_theme.page_cookie_policy_record"
TERMS = ("vela_setup/data/terms_en.html", "vela_setup/data/terms_fr.html")
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


# French labels (website language 2) for records whose names come from code or the catalog.
FR = {
    "website.menu": {"Electronics": "Électronique", "Audio": "Audio", "Accessories": "Accessoires",
                     "Gaming": "Gaming", "Smart Home": "Maison connectée", "Bags & Cases": "Sacs & étuis"},
    "product.ribbon": {"Sale": "Promo", "Best Seller": "Meilleure vente", "New": "Nouveau",
                       "Limited": "Édition limitée", "Out of Stock": "Rupture de stock"},
    "delivery.carrier": {"Standard delivery": "Livraison standard", "Pick up in store": "Retrait en magasin"},
    "blog.blog": {"Our blog": "Notre blog"},
}
FR_FILE = "vela_setup/data/fr_names.json"   # categories, attributes: too many for this file


class VelaSetup(models.AbstractModel):
    _name = "vela.setup"
    _description = "Vela Tech reproducible store settings"

    @api.model
    def apply(self):
        """Idempotent. Runs on every install/upgrade of vela_setup (data/setup.xml)."""
        self._apply_languages()
        self._apply_company()
        self._apply_website()
        self._apply_taxes()
        self._apply_payments()
        self._apply_terms()
        self._apply_french()
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
        for field in ("email", "website", "street", "zip", "city", "phone"):
            if not company[field]:
                vals[field] = COMPANY[field]
        if not company.country_id:
            vals["country_id"] = self.env.ref("base.tn").id
        company.write(vals)
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
        if warehouse and warehouse.name != WAREHOUSE_NAME:
            warehouse.name = WAREHOUSE_NAME
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
            policy = self.env.ref(COOKIE_POLICY_PAGE)
            # the policy page must be set before cookies_bar, or Odoo creates its own copy
            website.write({"cookie_policy_id": policy.id})
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

    def _sale_tax(self):
        company = self.env.company
        return self.env["account.tax"].search([
            ("company_id", "=", company.id), ("type_tax_use", "=", "sale"),
            ("amount_type", "=", "percent"), ("amount", "=", SALE_TAX_PERCENT),
        ], limit=1)

    def _apply_taxes(self):
        registry = self.env.registry
        if not self.env.company.chart_template and hasattr(registry, "_auto_install_template"):
            # Fresh DB: account would load the Tunisian chart (and its taxes) only after the
            # whole install, i.e. after this method. Load it now so products get the VAT.
            registry._auto_install_template(self.env)
            del registry._auto_install_template
        tax = self._sale_tax()
        if not tax:
            _logger.warning("vela_setup: no %s%% sale tax found (is l10n_tn installed?)", SALE_TAX_PERCENT)
            return
        company = self.env.company
        if company.account_sale_tax_id != tax:
            company.account_sale_tax_id = tax
        # every physical product we sell carries the VAT (gift cards, donations: no)
        products = self.env["product.template"].with_context(active_test=False).search(
            [("type", "=", "consu"), ("sale_ok", "=", True)])
        products.filtered(lambda p: p.taxes_id != tax).write({"taxes_id": [(6, 0, tax.ids)]})

    def _apply_payments(self):
        providers = self.env["payment.provider"].with_context(active_test=False)
        allowed = providers.search([("code", "=", "custom"), ("custom_mode", "in", PAY_ON_DELIVERY)])
        (providers.search([("active", "=", True)]) - allowed).write({"is_published": False, "active": False})
        for mode in PAY_ON_DELIVERY:
            provider = providers.search([("code", "=", "custom"), ("custom_mode", "=", mode)], limit=1)
            if not provider:
                _logger.warning("vela_setup: no %s payment provider", mode)
                continue
            name_en, name_fr, msg_en, msg_fr = PAYMENT_TEXT[mode]
            provider.write({"name": name_en, "state": "enabled"} if "state" in provider._fields
                           else {"name": name_en, "active": True})
            provider.write({"is_published": True, "pending_msg": f"<p>{msg_en}</p>"})
            provider.update_field_translations("name", {"fr_FR": name_fr})
            self._translate_html(provider, "pending_msg", f"<p>{msg_fr}</p>")
            provider.payment_method_ids.write({"active": True})
        # home delivery is paid in cash to the courier
        carriers = self.env["delivery.carrier"].search([("delivery_type", "in", ("fixed", "base_on_rule"))])
        carriers.filtered(lambda c: not c.allow_cash_on_delivery).write({"allow_cash_on_delivery": True})

    def _apply_terms(self):
        """Terms of sale: /terms page and invoices (account's html terms)."""
        self.env["ir.config_parameter"].sudo().set_bool("account.use_invoice_terms", True)
        with file_open(TERMS[0]) as f_en, file_open(TERMS[1]) as f_fr:
            html_en, html_fr = f_en.read(), f_fr.read()
        company = self.env.company
        company.write({"terms_type": "html", "invoice_terms_html": html_en})
        self._translate_html(company, "invoice_terms_html", html_fr)

    def _translate_html(self, record, fname, html_fr):
        """HTML fields are translated term by term (each text block). Both versions share
        the same structure, so terms pair up in order."""
        field = record._fields[fname]
        en, fr = [], []
        field.translate(en.append, record.with_context(lang="en_US")[fname])
        field.translate(fr.append, html_fr)
        try:
            pairs = dict(zip(en, fr, strict=True))
        except ValueError:
            _logger.warning("vela_setup: %s.%s FR and EN have different blocks: not translated",
                            record._name, fname)
            return
        record.update_field_translations(fname, {"fr_FR": pairs})

    def _apply_french(self):
        with file_open(FR_FILE) as f:
            names = {**FR, **json.load(f)}
        for model, mapping in names.items():
            for rec in self.env[model].with_context(lang="en_US").search([("name", "in", list(mapping))]):
                rec.update_field_translations("name", {"fr_FR": mapping[rec.name]})
