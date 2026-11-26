{
    "name": "Vela Analytics",
    "summary": "Consent-aware event tracking for the Vela Tech store: browser and trusted "
               "server events (vela.events.v1) stored with a durable outbox.",
    "description": """
docs/plans/0001-vela-analytics.md: A capture, B delivery, C local metrics and alerts.

- Browser events (page/product views, data-track clicks, checkout start, form errors),
  held in memory until the visitor accepts optional cookies.
- Trusted server events: search, add_to_cart, checkout errors, order_confirmed.
- One outbox row per event, delivered to the Kafka HTTP bridge (or kept local).
- 5-minute metrics, anomaly alerts with evidence, demo traffic generator.
""",
    "version": "20.0.1.1.0",
    "category": "Website/Website",
    "author": "Vela Tech study project",
    "license": "LGPL-3",
    "depends": ["website_sale", "website_sale_stock", "payment"],
    "data": [
        "security/analytics_security.xml",
        "security/ir.access.csv",
        "data/ir_cron.xml",
        "views/event_views.xml",
        "views/outbox_views.xml",
        "views/metric_views.xml",
        "views/alert_views.xml",
        "views/demo_wizard_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "vela_analytics/static/src/js/tracker.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
