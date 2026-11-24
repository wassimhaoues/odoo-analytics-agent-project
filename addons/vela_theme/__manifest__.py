{
    "name": "Vela Tech Theme",
    "summary": "Vela Tech look & feel: Sidi Bou Said palette, Archivo + Martian Mono, "
               "glass header, footer, logo, motion (Lenis + GSAP) and tracking hooks.",
    "description": """
Not a `theme_*` module on purpose (ADR 0005): Odoo only applies `theme_*` modules through
the theme picker, while this one installs/upgrades like any addon, so every developer
gets the identical site from git.
""",
    "version": "20.0.1.0.0",
    "category": "Website/Website",
    "author": "Vela Tech study project",
    "license": "LGPL-3",
    "depends": ["website_sale", "website_mass_mailing", "website_sale_collect"],
    "data": [
        "views/header.xml",
        "views/footer.xml",
        "views/home.xml",
        "views/shop.xml",
        "views/empty.xml",
        "views/dark_mode.xml",
        "views/pages.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            "vela_theme/static/src/scss/primary_variables.scss",
        ],
        "web.assets_frontend": [
            "vela_theme/static/src/scss/fonts.scss",
            "vela_theme/static/src/scss/tokens.scss",
            "vela_theme/static/src/scss/base.scss",
            "vela_theme/static/src/scss/header.scss",
            "vela_theme/static/src/scss/footer.scss",
            "vela_theme/static/src/scss/home.scss",
            "vela_theme/static/src/scss/shop.scss",
            "vela_theme/static/src/scss/checkout.scss",
            "vela_theme/static/src/scss/pages.scss",
            "vela_theme/static/src/scss/dark.scss",
            # vendored motion libs (ADR 0006), loaded before our interactions
            "vela_theme/static/lib/gsap-3.12.5/gsap.min.js",
            "vela_theme/static/lib/gsap-3.12.5/ScrollTrigger.min.js",
            "vela_theme/static/lib/lenis-1.1.13/lenis.min.js",
            "vela_theme/static/src/js/tracking_annotations.js",
            "vela_theme/static/src/js/home_motion.js",
            "vela_theme/static/src/js/shop_tracking.js",
            "vela_theme/static/src/js/shop_motion.js",
            "vela_theme/static/src/js/theme_toggle.js",
            "vela_theme/static/src/xml/stock_message.xml",
        ],
    },
    "installable": True,
    "application": False,
}
