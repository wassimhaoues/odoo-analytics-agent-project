from odoo import models


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _set_error(self, state_message, extra_allowed_states=()):
        txs = super()._set_error(state_message, extra_allowed_states=extra_allowed_states)
        Event = self.env["vela.analytics.event"]
        for order in txs.sale_order_ids.filtered("website_id"):
            Event._emit_server("checkout_error", error_code="payment_error", sale_order_id=order.id)
        return txs
