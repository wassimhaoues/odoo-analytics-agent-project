from odoo.addons.website_sale.tests.common import WebsiteSaleCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install", "vela")
class TestOrderEvent(WebsiteSaleCommon):
    def order(self, qty=1, **vals):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": qty})],
            **vals,
        })

    def events(self, order):
        return self.env["vela.analytics.event"].sudo().search([
            ("sale_order_id", "=", order.id), ("event", "=", "order_confirmed")])

    def test_order_confirmed_once(self):  # T3, FR-02
        order = self.order(qty=2)
        order.sudo().action_confirm()
        event = self.events(order)
        self.assertEqual(len(event), 1)
        self.assertEqual(event.quantity, 2)
        self.assertFalse(event.consent)  # no visit was linked: no session, no visitor
        self.assertFalse(event.session)
        self.assertEqual(event.outbox_ids.state, "pending")
        event.sale_order_id._vela_order_confirmed()  # re-run: deterministic id, no duplicate
        self.assertEqual(len(self.events(order)), 1)

    def test_linked_with_consent(self):
        order = self.order(vela_session="11111111-1111-4111-8111-111111111111",
                           vela_visitor="abcdef0123456789")
        order.sudo().action_confirm()
        event = self.events(order)
        self.assertTrue(event.consent)
        self.assertEqual(event.session, order.vela_session)

    def test_backend_order_not_tracked(self):
        order = self.order(website_id=False)
        order.sudo().action_confirm()
        self.assertFalse(self.events(order))
