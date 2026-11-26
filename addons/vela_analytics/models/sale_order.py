import logging

from odoo import fields, models

from ..services import validation as V

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # Set at add_to_cart, only with consent: links the confirmed order to the visit even when
    # confirmation happens outside the visitor's request (plan §4).
    vela_session = fields.Char(copy=False, readonly=True)
    vela_visitor = fields.Char(copy=False, readonly=True)

    def _vela_remember_visit(self, ctx):
        if ctx and ctx["consent"] and ctx["session"] and self.vela_session != ctx["session"]:
            self.sudo().write({"vela_session": ctx["session"], "vela_visitor": ctx["visitor"]})

    def _action_confirm(self):
        res = super()._action_confirm()
        self.filtered("website_id")._vela_order_confirmed()
        return res

    def _vela_order_confirmed(self):
        """Trusted order_confirmed (FR-02, D2): always recorded, linked only with consent."""
        Event = self.env["vela.analytics.event"].sudo()  # sudo: confirmation may run as public
        if Event._tracking_paused():
            return
        try:
            with self.env.cr.savepoint():
                Event._record([order._vela_order_event_vals() for order in self])
        except Exception:  # noqa: BLE001 - tracking must never block a confirmation (T6)
            _logger.exception("vela_analytics: could not record order_confirmed")

    def _vela_order_event_vals(self):
        lines = self.order_line.filtered(lambda line: not line.display_type and not line.is_delivery)
        ctx = self.env["vela.analytics.event"]._request_context() or {}
        consent = bool(self.vela_session)
        return {
            "event_id": V.order_event_id(self.name),
            "event": "order_confirmed",
            "occurred_at": fields.Datetime.now(),
            "origin": "server",
            "website_id": self.website_id.id,
            "sale_order_id": self.id,
            "quantity": int(sum(lines.mapped("product_uom_qty"))),
            "device": ctx.get("device") if consent else False,
            "consent": consent,
            "session": self.vela_session or False,
            "visitor": self.vela_visitor or False,
        }

    def _is_cart_ready_for_delivery(self):
        ready = super()._is_cart_ready_for_delivery()
        if not ready:
            self.env["vela.analytics.event"]._emit_server(
                "checkout_error", error_code="delivery_unavailable", sale_order_id=self.id,
            )
        return ready


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _check_availability(self):
        available = super()._check_availability()
        if not available:
            Event = self.env["vela.analytics.event"]
            sku, variant = Event._sku_of(self.product_id)
            Event._emit_server(
                "checkout_error", error_code="out_of_stock", sale_order_id=self.order_id.id,
                product_id=self.product_id.id, sku=sku,
                payload={"variant": variant} if variant else None,
                quantity=int(self.product_uom_qty),
            )
        return available
