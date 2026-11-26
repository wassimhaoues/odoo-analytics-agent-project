import uuid
from datetime import datetime, timedelta

from odoo.tests import BaseCase, TransactionCase, tagged

from ..services import metrics as M

T = dict(M.THRESHOLDS)


@tagged("post_install", "-at_install", "vela")
class TestRules(BaseCase):
    def test_windows(self):
        dt = datetime(2026, 11, 24, 10, 7, 33)
        self.assertEqual(M.floor_window(dt), datetime(2026, 11, 24, 10, 5))
        wins = M.windows_between(datetime(2026, 11, 24, 10, 0), datetime(2026, 11, 24, 10, 17))
        self.assertEqual([w.minute for w in wins], [0, 5, 10])  # 10:15 not closed yet

    def test_checkout_error_rule(self):
        base = [0.05] * 12
        self.assertTrue(M.checkout_error_rule(10, 25, base, T))      # 0.40 ≥ 2 × 0.05
        self.assertIsNone(M.checkout_error_rule(4, 25, base, T))     # < 5 errors
        self.assertIsNone(M.checkout_error_rule(10, 19, base, T))    # < 20 starts
        self.assertIsNone(M.checkout_error_rule(10, 25, [0.05], T))  # no history, no claim
        self.assertIsNone(M.checkout_error_rule(6, 25, [0.20] * 12, T))  # 0.24 < 0.40
        self.assertEqual(M.checkout_error_rule(20, 25, base, T)["severity"], "high")

    def test_demand_and_zero_search_rules(self):
        self.assertTrue(M.demand_rule(12, [0, 1, 0, 2], T))
        self.assertIsNone(M.demand_rule(9, [0] * 12, T))             # < min adds
        self.assertIsNone(M.demand_rule(12, [11, 12, 13] * 4, T))    # usual for this product
        self.assertTrue(M.zero_search_rule(12, [1, 0, 1], T))
        self.assertIsNone(M.zero_search_rule(12, [5] * 12, T))       # 12 < 3 × 5


@tagged("post_install", "-at_install", "vela")
class TestMetrics(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["vela.analytics.event"]
        cls.Metric = cls.env["vela.analytics.metric"]
        cls.Alert = cls.env["vela.analytics.alert"]
        cls.website = cls.env["website"].search([], limit=1)
        # far in the past: never collides with real or demo data in the test DB
        cls.t0 = datetime(2020, 1, 6, 12, 0)

    def add(self, event, n=1, at=0, synthetic=False, **vals):
        self.Event.sudo()._record([{
            "event_id": str(uuid.uuid4()), "event": event, "origin": "server",
            "occurred_at": self.t0 + timedelta(minutes=at, seconds=i % 60),
            "website_id": self.website.id, "session": str(uuid.uuid4()),
            "device": "mobile", "is_synthetic": synthetic, **vals,
        } for i in range(n)], outbox=False)

    def metric(self, key, segment="all", at=0, dataset="real"):
        return self.Metric.search([("metric_key", "=", key), ("segment", "=", segment),
                                   ("window_start", "=", self.t0 + timedelta(minutes=at)),
                                   ("dataset", "=", dataset)])

    def compute(self, start=0, end=5):
        self.Metric._compute_range(self.t0 + timedelta(minutes=start),
                                   self.t0 + timedelta(minutes=end))

    def test_counts_ratio_idempotent(self):
        self.add("checkout_started", 20)
        self.add("checkout_error", 5, error_code="payment_error")
        self.add("add_to_cart", 3, sku="VT-TST-001")
        self.add("search", 2, search_results_count=0)
        self.add("page_view", 4, synthetic=True)  # demo: other dataset
        self.compute()
        self.assertEqual(self.metric("events.checkout_started").value, 20)
        self.assertEqual(self.metric("events.checkout_started", "device:mobile").value, 20)
        ratio = self.metric("checkout_error_ratio")
        self.assertEqual((ratio.numerator, ratio.denominator, ratio.value), (5, 20, 0.25))
        self.assertEqual(self.metric("add_to_cart", "product:VT-TST-001").value, 3)
        self.assertEqual(self.metric("search_zero_results").value, 2)
        self.assertFalse(self.metric("events.page_view"))
        self.assertEqual(self.metric("events.page_view", dataset="demo").value, 4)
        rows = self.Metric.search_count([("window_start", "=", self.t0)])
        self.add("checkout_started", 2, at=1)  # late event in the same window
        self.compute()
        self.assertEqual(self.Metric.search_count([("window_start", "=", self.t0)]), rows)
        self.assertEqual(self.metric("checkout_error_ratio").denominator, 22)

    def test_checkout_error_spike_alert(self):  # T4 (tracker part)
        for w in range(12):  # one hour of normal traffic: 1 error per 20 starts
            self.add("checkout_started", 20, at=w * 5)
            self.add("checkout_error", 1, at=w * 5, error_code="form_validation")
        self.add("checkout_started", 25, at=60)
        self.add("checkout_error", 12, at=60, error_code="payment_error")
        self.compute(0, 65)
        alert = self.Alert.search([("alert_type", "=", "checkout_error_spike"),
                                   ("segment", "=", "all")])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.window_start, self.t0 + timedelta(minutes=60))
        self.assertAlmostEqual(alert.measured, 0.48)
        self.assertAlmostEqual(alert.baseline, 0.05)
        self.assertEqual(alert.evidence["checkout_errors"], 12)
        self.assertEqual(alert.evidence["baseline_windows"], 12)
        self.assertEqual((alert.dataset, alert.status), ("real", "new"))
        alert.action_acknowledge()
        self.compute(60, 65)  # recompute keeps one alert and its status
        again = self.Alert.search([("alert_type", "=", "checkout_error_spike"),
                                   ("segment", "=", "all")])
        self.assertEqual((again, again.status), (alert, "acknowledged"))

    def test_demand_and_zero_search_alerts(self):
        self.add("add_to_cart", 1, at=0, sku="VT-TST-002")
        self.add("add_to_cart", 15, at=60, sku="VT-TST-002")
        self.add("search", 14, at=60, search_results_count=0)
        self.compute(0, 65)
        types = set(self.Alert.search([("window_start", "=", self.t0 + timedelta(minutes=60))])
                    .mapped("alert_type"))
        self.assertEqual(types, {"demand_spike", "zero_result_search_spike"})

    def test_freshness(self):
        self.add("page_view")
        self.compute()
        self.assertFalse(self.Metric._freshness()["stale"])
        self.Metric.search([]).write({"computed_at": datetime(2020, 1, 1)})
        self.assertTrue(self.Metric._freshness()["stale"])


@tagged("post_install", "-at_install", "vela")
class TestDemo(TransactionCase):
    def test_checkout_error_spike_scenario(self):  # spec T4: seed a spike, get an alert
        Demo = self.env["vela.analytics.demo"]
        if not Demo._catalog():
            self.env["product.product"].create({
                "name": "Demo probe", "default_code": "VT-DEMO-001", "website_published": True,
                "sale_ok": True, "type": "consu"})
        result = Demo._generate("checkout_error_spike", minutes=90, volume=20, seed=7)
        self.assertGreater(result["events"], 500)
        events = self.env["vela.analytics.event"].search([("origin", "=", "demo")])
        self.assertTrue(all(events.mapped("is_synthetic")))
        self.assertFalse(events.outbox_ids)  # not sent to the pipeline unless asked
        alerts = self.env["vela.analytics.alert"].browse(result["alert_ids"])
        self.assertIn("checkout_error_spike", alerts.mapped("alert_type"))
        self.assertEqual(set(alerts.mapped("dataset")), {"demo"})
        self.assertFalse(self.env["vela.analytics.alert"].search([
            ("dataset", "=", "real"), ("alert_type", "=", "checkout_error_spike"),
            ("window_start", ">=", datetime.now() - timedelta(hours=2))]))
        counts = Demo._clear()
        self.assertEqual(counts["vela.analytics.event"], len(events))
        self.assertFalse(self.env["vela.analytics.metric"].search([("dataset", "=", "demo")]))

    def test_paused_tracking_records_nothing(self):
        self.env["ir.config_parameter"].sudo().set_bool("vela_analytics.tracking_paused", True)
        partner = self.env["res.partner"].create({"name": "Buyer"})
        product = self.env["product.product"].create({"name": "P", "list_price": 10})
        order = self.env["sale.order"].create({
            "partner_id": partner.id, "website_id": self.env["website"].search([], limit=1).id,
            "order_line": [(0, 0, {"product_id": product.id})]})
        order.action_confirm()
        self.assertFalse(self.env["vela.analytics.event"].search([("sale_order_id", "=", order.id)]))
