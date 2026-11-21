import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.analytics_outbox import MAX_ATTEMPTS
from .fake_bridge import FakeBridge

TOKEN = "test-token"


@tagged("post_install", "-at_install", "vela")
class TestOutbox(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bridge = FakeBridge(token=TOKEN).start()
        cls.addClassCleanup(cls.bridge.stop)
        cls.Outbox = cls.env["vela.analytics.outbox"]
        cls.website = cls.env["website"].search([], limit=1)

    def setUp(self):
        super().setUp()
        self.bridge.fail_status = None
        self.bridge.reject_ids.clear()
        self.bridge.received.clear()
        self.bridge.seen.clear()
        self.Outbox.search([]).unlink()  # only this test's rows are due

    def env_mode(self, mode="bridge", url=None, token=TOKEN):
        return patch.dict(os.environ, {"VELA_DELIVERY_MODE": mode,
                                       "VELA_BRIDGE_URL": url or self.bridge.url,
                                       "VELA_BRIDGE_TOKEN": token})

    def make(self, n=1, **vals):
        return self.env["vela.analytics.event"].sudo()._record([{
            "event_id": str(uuid.uuid4()), "event": "page_view", "origin": "server",
            "occurred_at": fields.Datetime.now(), "website_id": self.website.id,
            "session": str(uuid.uuid4()), "page": "/shop", **vals,
        } for _ in range(n)]).outbox_ids

    def deliver(self):
        return self.Outbox._deliver_batch()

    def test_local_mode_no_network(self):  # FR-07: Odoo works alone
        rows = self.make(3)
        with self.env_mode("local"), patch.object(requests.Session, "send",
                                                  side_effect=AssertionError("network")):
            self.assertEqual(self.deliver(), 3)
        self.assertEqual(set(rows.mapped("state")), {"sent"})
        self.assertEqual(set(rows.mapped("channel")), {"local"})

    def test_bridge_delivers_envelopes(self):  # IN-01 (Odoo side)
        rows = self.make(2)
        rows |= self.make(event="order_confirmed", session=False)  # no consent: no session
        with self.env_mode():
            self.deliver()
        self.assertEqual(set(rows.mapped("state")), {"sent"})
        self.assertEqual(set(rows.mapped("channel")), {"bridge"})
        got = {e["event_id"]: e for e in self.bridge.received}
        self.assertEqual(set(got), set(rows.mapped("event_id")))
        order = got[rows[-1].event_id]
        self.assertNotIn("session", order)
        self.assertEqual(order["origin"], "server")
        self.assertIs(order["is_synthetic"], False)
        self.assertTrue(order["ts"].endswith("Z"))

    def test_outage_then_recovery(self):  # T6, IN-03
        rows = self.make(2)
        closed = FakeBridge()  # bind a free port, then close it: connection refused
        closed.stop()
        with self.env_mode(url=closed.url):
            self.deliver()
        self.assertEqual(set(rows.mapped("state")), {"failed"})
        self.assertEqual(rows[0].attempts, 1)
        self.assertGreater(rows[0].next_retry_at, fields.Datetime.now() + timedelta(minutes=1))
        self.assertIn("unreachable", rows[0].last_error)
        with self.env_mode():
            self.assertEqual(self.deliver(), 0)  # not due yet: backoff respected
            rows.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
            self.deliver()
        self.assertEqual(set(rows.mapped("state")), {"sent"})

    def test_server_error_and_bad_token_retry(self):
        rows = self.make()
        self.bridge.fail_status = 503
        with self.env_mode():
            self.deliver()
        self.assertEqual((rows.state, rows.last_error), ("failed", "bridge error 503"))
        self.bridge.fail_status = None
        rows.next_retry_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.env_mode(token="wrong"):
            self.deliver()
        self.assertEqual(rows.state, "failed")
        self.assertIn("401", rows.last_error)

    def test_rejected_dead_and_duplicate_sent(self):
        rows = self.make(2)
        self.bridge.reject_ids.add(rows[0].event_id)
        self.bridge.seen.add(rows[1].event_id)  # already in Kafka: a retry after a lost answer
        with self.env_mode():
            self.deliver()
        self.assertEqual(rows[0].state, "dead")
        self.assertIn("rejected", rows[0].last_error)
        self.assertEqual(rows[1].state, "sent")

    def test_dead_after_max_attempts_and_retry_button(self):
        rows = self.make()
        rows.write({"attempts": MAX_ATTEMPTS - 1})
        self.bridge.fail_status = 500
        with self.env_mode():
            self.deliver()
        self.assertEqual(rows.state, "dead")
        rows.action_retry()
        self.assertEqual((rows.state, rows.attempts), ("pending", 0))
        self.bridge.fail_status = None
        with self.env_mode():
            self.deliver()
        self.assertEqual(rows.state, "sent")

    def test_backoff_grouped_by_attempts(self):
        rows = self.make(2)
        rows[0].attempts = 3
        self.bridge.fail_status = 500
        with self.env_mode():
            self.deliver()
        self.assertEqual(rows.mapped("attempts"), [4, 1])
        delay = (rows[0].next_retry_at - fields.Datetime.now()).total_seconds() / 60
        self.assertAlmostEqual(delay, 16, delta=1)

    def test_checkout_never_calls_the_network(self):  # T6: Kafka down, sales go on
        partner = self.env["res.partner"].create({"name": "Buyer"})
        product = self.env["product.product"].create({"name": "P", "list_price": 10})
        order = self.env["sale.order"].create({
            "partner_id": partner.id, "website_id": self.website.id,
            "order_line": [(0, 0, {"product_id": product.id})],
        })
        with self.env_mode(url="http://localhost:1"), patch.object(
                requests.Session, "send", side_effect=AssertionError("network in checkout")):
            order.action_confirm()
        event = self.env["vela.analytics.event"].search([("sale_order_id", "=", order.id)])
        self.assertEqual(event.outbox_ids.state, "pending")
