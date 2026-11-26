"""Synthetic traffic for demos and spec test T4 (plan §11, D7, D10).

Every event is is_synthetic=True, origin=demo: metrics and alerts keep it in the "demo"
dataset, apart from real reporting. Used by the wizard and scripts/analytics_demo.sh.
"""
import random
import uuid
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services import metrics as M

SCENARIOS = [
    ("normal", "Normal traffic"),
    ("checkout_error_spike", "Checkout error spike"),
    ("demand_spike", "Demand spike on one product"),
    ("zero_result_search", "Zero-result search spike"),
]
SPIKE_WINDOWS = 3  # the anomaly covers the last 15 minutes
DEVICES = (["mobile"] * 6) + (["desktop"] * 3) + ["tablet"]


class VelaAnalyticsDemo(models.AbstractModel):
    _name = "vela.analytics.demo"
    _description = "Analytics demo traffic generator"

    @api.model
    def _generate(self, scenario="normal", minutes=120, volume=20, sku=None,
                  to_pipeline=False, seed=None):
        """Create `minutes` of closed 5-minute windows of traffic ending now, then compute
        their metrics and alerts. Returns a summary dict."""
        if scenario not in dict(SCENARIOS):
            raise UserError(self.env._("Unknown scenario %s", scenario))
        minutes, volume = max(15, min(int(minutes), 24 * 60)), max(1, min(int(volume), 200))
        rng = random.Random(seed)
        catalog = self._catalog()
        if not catalog:
            raise UserError(self.env._("No published product with an internal reference to simulate."))
        if scenario == "demand_spike":
            sku = sku or rng.choice(catalog)[0]
            if sku not in dict(catalog):
                raise UserError(self.env._("No published product with SKU %s", sku))
        website = self.env["website"].search([], limit=1)
        end = M.floor_window(fields.Datetime.now())
        windows = M.windows_between(end - timedelta(minutes=minutes), end)
        spike_from = windows[-SPIKE_WINDOWS] if len(windows) >= SPIKE_WINDOWS else windows[0]

        events = []
        for window_start in windows:
            gen = _Window(rng, window_start, website.id, catalog)
            for _i in range(volume):
                gen.visit()
            if window_start >= spike_from:
                gen.spike(scenario, volume, sku)
            events += gen.events
        Event = self.env["vela.analytics.event"].sudo()  # demo data written by a manager/script
        created = Event._record(events, outbox=to_pipeline)
        self.env["vela.analytics.metric"]._compute_range(windows[0], end)
        alerts = self.env["vela.analytics.alert"].search([
            ("dataset", "=", "demo"), ("window_start", ">=", spike_from)])
        return {"scenario": scenario, "events": len(created), "windows": len(windows),
                "sku": sku, "alerts": alerts.mapped("name"), "alert_ids": alerts.ids}

    @api.model
    def _catalog(self):
        """[(theme SKU, product page path)] for published products with a code."""
        products = self.env["product.product"].sudo().search([
            ("website_published", "=", True), ("sale_ok", "=", True),
            ("default_code", "!=", False)], limit=500)
        Event = self.env["vela.analytics.event"]
        out = {}
        for product in products:
            sku, _variant = Event._sku_of(product)
            if sku:
                out.setdefault(sku, product.product_tmpl_id.website_url or "/shop")
        return list(out.items())

    @api.model
    def _clear(self):
        """Delete every synthetic event and every demo metric/alert."""
        counts = {}
        for model, domain in (("vela.analytics.event", [("is_synthetic", "=", True)]),
                              ("vela.analytics.metric", [("dataset", "=", "demo")]),
                              ("vela.analytics.alert", [("dataset", "=", "demo")])):
            records = self.env[model].sudo().search(domain)
            counts[model] = len(records)
            records.unlink()
        return counts


class _Window:
    """Builds the events of one 5-minute window."""

    def __init__(self, rng, window_start, website_id, catalog):
        self.rng, self.start, self.website_id, self.catalog = rng, window_start, website_id, catalog
        self.events = []

    def _session(self):
        return str(uuid.uuid4()), self.rng.choice(DEVICES), self.rng.uniform(0, 200)

    def _add(self, session, device, offset, event, **vals):
        offset = min(offset, 299)
        self.events.append({
            "event_id": str(uuid.uuid4()), "event": event, "origin": "demo",
            "is_synthetic": True, "consent": True, "session": session, "device": device,
            "website_id": self.website_id, "occurred_at": self.start + timedelta(seconds=offset),
            **vals,
        })

    def visit(self):
        rng = self.rng
        session, device, t = self._session()
        self._add(session, device, t, "page_view", page="/")
        if rng.random() < 0.2:
            results = 0 if rng.random() < 0.1 else rng.randint(1, 30)
            self._add(session, device, t + 5, "search", page="/shop", search_results_count=results)
        cart = []
        for step in range(rng.randint(1, 3)):
            sku, path = rng.choice(self.catalog)
            t += rng.uniform(5, 20)
            self._add(session, device, t, "page_view", page=path)
            self._add(session, device, t + 1, "product_view", page=path, sku=sku)
            if rng.random() < 0.4 / (step + 1):
                self._add(session, device, t + 3, "click", page=path, sku=sku,
                          track="product.add_to_cart")
                self._add(session, device, t + 4, "add_to_cart", page=path, sku=sku, quantity=1)
                cart.append(sku)
        if cart and rng.random() < 0.6:
            self._checkout(session, device, t + 10, error_rate=0.05, codes=(
                "form_validation", "address_invalid"))

    def _checkout(self, session, device, t, error_rate, codes):
        self._add(session, device, t, "checkout_started", page="/shop/checkout")
        if self.rng.random() < error_rate:
            self._add(session, device, t + 20, "checkout_error", page="/shop/payment",
                      error_code=self.rng.choice(codes))
        elif self.rng.random() < 0.6:
            self._add(session, device, t + 30, "order_confirmed", page="/shop/confirmation",
                      quantity=1)

    def spike(self, scenario, volume, sku):
        extra = max(12, int(volume * 1.5))
        for _i in range(extra):
            session, device, t = self._session()
            if scenario == "checkout_error_spike":
                self._checkout(session, device, t, error_rate=0.5, codes=("payment_error",))
            elif scenario == "demand_spike":
                path = dict(self.catalog)[sku]
                self._add(session, device, t, "product_view", page=path, sku=sku)
                self._add(session, device, t + 3, "add_to_cart", page=path, sku=sku, quantity=1)
            elif scenario == "zero_result_search":
                self._add(session, device, t, "search", page="/shop", search_results_count=0)


class VelaAnalyticsDemoWizard(models.TransientModel):
    _name = "vela.analytics.demo.wizard"
    _description = "Generate demo traffic"

    scenario = fields.Selection(SCENARIOS, required=True, default="checkout_error_spike")
    minutes = fields.Integer(default=120, help="History to generate, ending now (15 to 1440).")
    volume = fields.Integer(default=20, help="Visits per 5-minute window (1 to 200).")
    product_id = fields.Many2one(
        "product.product", domain=[("website_published", "=", True), ("default_code", "!=", False)],
        help="Product for the demand spike (random if empty).",
    )
    to_pipeline = fields.Boolean(
        "Also send to the pipeline",
        help="Create outbox rows so the demo events also go to Kafka (flagged is_synthetic).",
    )

    def action_generate(self):
        self.ensure_one()
        sku = self.product_id and self.env["vela.analytics.event"]._sku_of(self.product_id)[0]
        result = self.env["vela.analytics.demo"]._generate(
            self.scenario, self.minutes, self.volume, sku=sku or None,
            to_pipeline=self.to_pipeline)
        action = self.env["ir.actions.act_window"]._for_xml_id("vela_analytics.action_alerts")
        action["context"] = {"search_default_demo": 1}
        action["display_name"] = self.env._("Demo alerts: %(n)s events generated", n=result["events"])
        return action

    def action_clear(self):
        counts = self.env["vela.analytics.demo"]._clear()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {
            "type": "success", "sticky": False,
            "message": self.env._("Deleted %(e)s demo events, %(m)s metrics, %(a)s alerts.",
                         e=counts["vela.analytics.event"], m=counts["vela.analytics.metric"],
                         a=counts["vela.analytics.alert"]),
            "next": {"type": "ir.actions.act_window_close"}}}
