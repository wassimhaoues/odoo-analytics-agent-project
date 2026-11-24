import json
import re
import uuid

from odoo.tests import HttpCase, tagged

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"


@tagged("post_install", "-at_install", "vela")
class TestServerEvents(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create({
            "name": "Vela Probe Laptop", "default_code": "VT-TST-001", "list_price": 100,
            "type": "consu", "website_published": True, "sale_ok": True,
        })

    def setUp(self):
        super().setUp()
        self.session = str(uuid.uuid4())
        self.opener.headers["User-Agent"] = UA

    def consent(self):
        self.opener.cookies.set("website_cookies_bar",
                                json.dumps({"required": True, "optional": True}))
        self.opener.cookies.set("vela_session", self.session)

    def events(self, event):
        return self.env["vela.analytics.event"].sudo().search([("event", "=", event)])

    def add_to_cart(self):
        return self.make_jsonrpc_request("/shop/cart/add", {
            "product_template_id": self.product.product_tmpl_id.id,
            "product_id": self.product.id, "quantity": 2,
        })

    def test_search_counts_results_never_text(self):
        self.consent()
        self.url_open("/shop?search=Vela+Probe")
        event = self.events("search")
        self.assertEqual(len(event), 1)
        self.assertGreaterEqual(event.search_results_count, 1)
        self.assertEqual(event.device, "mobile")
        self.assertEqual(event.page, "/shop")
        self.assertNotIn("Probe", json.dumps(event._to_envelope()))

    def test_add_to_cart_links_order_to_visit(self):  # T3 link
        self.consent()
        self.add_to_cart()
        event = self.events("add_to_cart")
        self.assertEqual(len(event), 1)
        self.assertEqual((event.sku, event.quantity, event.session),
                         ("VT-TST-001", 2, self.session))
        self.assertEqual(event.sale_order_id.vela_session, self.session)
        self.assertEqual(event.sale_order_id.vela_visitor, event.visitor)

    def test_no_consent_no_server_events(self):  # T2, D2
        self.url_open("/shop?search=Vela+Probe")
        self.add_to_cart()
        self.assertFalse(self.events("search") | self.events("add_to_cart"))
        order = self.env["sale.order"].sudo().search([], order="id desc", limit=1)
        self.assertFalse(order.vela_session)

    def test_address_errors(self):
        self.consent()
        self.add_to_cart()
        page = self.url_open("/shop/address").text
        token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
        res = self.url_open("/shop/address/submit",
                            data={"name": "", "email": "nope", "csrf_token": token})
        self.assertEqual(res.status_code, 200)  # the shop still answers normally
        event = self.events("checkout_error")
        self.assertEqual(event.error_code, "address_invalid")
        self.assertTrue(event.payload["fields"])
