from odoo import fields, models

P = "vela_analytics."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vela_tracking_paused = fields.Boolean(
        "Pause tracking", config_parameter=P + "tracking_paused",
        help="Stop recording browser and server events (orders included). Demo data still works.")
    vela_retention_days = fields.Integer(
        "Keep raw events (days)", config_parameter=P + "retention_days", default=90)
    vela_checkout_error_factor = fields.Float(
        "Checkout error: × baseline", config_parameter=P + "checkout_error_factor", default=2.0)
    vela_checkout_error_min_errors = fields.Integer(
        "Checkout error: min errors", config_parameter=P + "checkout_error_min_errors", default=5)
    vela_checkout_error_min_starts = fields.Integer(
        "Checkout error: min checkout starts", config_parameter=P + "checkout_error_min_starts",
        default=20)
    vela_demand_sigma = fields.Float(
        "Demand: σ above mean", config_parameter=P + "demand_sigma", default=3.0)
    vela_demand_min_adds = fields.Integer(
        "Demand: min add-to-carts", config_parameter=P + "demand_min_adds", default=10)
    vela_zero_search_factor = fields.Float(
        "Zero-result search: × baseline", config_parameter=P + "zero_search_factor", default=3.0)
    vela_zero_search_min = fields.Integer(
        "Zero-result search: min searches", config_parameter=P + "zero_search_min", default=10)
