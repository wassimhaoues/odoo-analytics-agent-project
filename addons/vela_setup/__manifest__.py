{
    "name": "Vela Tech Setup",
    "summary": "One install = the whole Vela Tech store: every app we use, our addons, "
               "and the shared settings (company, website, languages, payments).",
    "description": """
Single source of truth for the store's *state*. Both developers build an identical
Odoo from git by installing this module (scripts/setup.sh).

Rule (.claude/rules/reproducibility.md): if you install an app or change a setting in the
UI, add it here too, or your teammate won't have it.
""",
    "version": "20.0.1.0.0",
    "category": "Hidden",
    "author": "Vela Tech study project",
    "license": "LGPL-3",
    "depends": [
        # localisation (DB is created with --country TN, this pins it)
        "l10n_tn",
        # store
        "website",
        "website_sale",
        "website_sale_stock",
        "website_sale_loyalty",
        "website_sale_mass_mailing",
        "website_sale_collect",
        "payment_demo",
        # operations
        "stock",
        "purchase",
        "sale_management",
        # marketing & customers
        "mass_mailing",
        "website_links",
        "crm",
        "website_crm",
        "website_livechat",
        "website_blog",
        "survey",
        # our addons
        "vela_theme",
        "vela_tech_catalog",
    ],
    "data": [
        "data/setup.xml",
    ],
    "installable": True,
    "application": False,
}
