import logging
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models

from ..services import metrics as M

_logger = logging.getLogger(__name__)

DATASETS = [("real", "Real"), ("demo", "Demo")]
SOURCES = [("local", "Odoo (local)"), ("pipeline", "Spark pipeline")]


class VelaAnalyticsMetric(models.Model):
    """5-minute KPI windows (plan §9). Same shape as the pipeline's output, so
    vela_ai_agent reads one format whatever computed it (source)."""

    _name = "vela.analytics.metric"
    _description = "Analytics Metric (5-minute window)"
    _order = "window_start desc, metric_key, segment"
    _rec_name = "metric_key"

    metric_key = fields.Char(required=True, readonly=True, index=True)
    window_start = fields.Datetime(required=True, readonly=True, index=True)
    window_end = fields.Datetime(required=True, readonly=True)
    segment = fields.Char(required=True, readonly=True, default="all",
                          help="all, device:<device>, product:<sku>")
    numerator = fields.Float(readonly=True)
    denominator = fields.Float(readonly=True)
    value = fields.Float(readonly=True, aggregator="avg")
    source = fields.Selection(SOURCES, required=True, default="local", readonly=True)
    dataset = fields.Selection(DATASETS, required=True, default="real", readonly=True, index=True)
    computed_at = fields.Datetime(readonly=True)

    _metric_uniq = models.Constraint(
        "unique (metric_key, window_start, segment, source, dataset)",
        "One value per metric, window, segment, source and dataset.",
    )

    # ---- settings -----------------------------------------------------------------------

    @api.model
    def _thresholds(self):
        params = self.env["ir.config_parameter"].sudo()
        return {key: params.get_float(f"vela_analytics.{key}", default)
                for key, default in M.THRESHOLDS.items()}

    # ---- computation --------------------------------------------------------------------

    @api.model
    def _cron_compute(self):
        """Every 5 minutes: the last closed windows (late events included), then alerts."""
        end = M.floor_window(fields.Datetime.now())
        self._compute_range(end - M.RECOMPUTE_WINDOWS * M.WINDOW, end)

    @api.model
    def _compute_range(self, start, end):
        windows = M.windows_between(start, end)
        for window_start in windows:
            for dataset, _label in DATASETS:
                self._compute_window(window_start, dataset)
        Alert = self.env["vela.analytics.alert"]
        for window_start in windows:  # chronological: each baseline uses earlier windows
            for dataset, _label in DATASETS:
                Alert._detect(window_start, dataset)
        return len(windows)

    @api.model
    def _compute_window(self, window_start, dataset):
        window_end = window_start + M.WINDOW
        Event = self.env["vela.analytics.event"]
        domain = [("occurred_at", ">=", window_start), ("occurred_at", "<", window_end),
                  ("is_synthetic", "=", dataset == "demo")]
        values = defaultdict(lambda: [0.0, 0.0])  # (key, segment) -> [numerator, denominator]
        starts, errors = defaultdict(int), defaultdict(int)
        for event, device, count in Event._read_group(domain, ["event", "device"], ["__count"]):
            for segment in ("all", f"device:{device}" if device else None):
                if not segment:
                    continue
                values[(f"events.{event}", segment)][0] += count
                if event == "checkout_started":
                    starts[segment] += count
                elif event == "checkout_error":
                    errors[segment] += count
        for segment in set(starts) | set(errors):
            values[("checkout_error_ratio", segment)] = [errors[segment], starts[segment]]
        for sku, count in Event._read_group(domain + [("event", "=", "add_to_cart"),
                                                      ("sku", "!=", False)],
                                            ["sku"], ["__count"]):
            values[("add_to_cart", f"product:{sku}")][0] = count
        zero = Event.search_count(domain + [("event", "=", "search"),
                                            ("search_results_count", "=", 0)])
        if zero:
            values[("search_zero_results", "all")][0] = zero
        self._upsert(window_start, window_end, dataset, values)

    @api.model
    def _upsert(self, window_start, window_end, dataset, values):
        """Idempotent: recomputing a window updates its rows, never duplicates them."""
        existing = {(m.metric_key, m.segment): m for m in self.search([
            ("window_start", "=", window_start), ("source", "=", "local"),
            ("dataset", "=", dataset)])}
        now = fields.Datetime.now()
        to_create = []
        for (key, segment), (num, den) in values.items():
            vals = {"numerator": num, "denominator": den, "computed_at": now,
                    "value": M.ratio(num, den) if key == "checkout_error_ratio" else num}
            if record := existing.pop((key, segment), None):
                record.write(vals)
            else:
                to_create.append({**vals, "metric_key": key, "segment": segment,
                                  "window_start": window_start, "window_end": window_end,
                                  "source": "local", "dataset": dataset})
        self.create(to_create)
        # a segment with no events any more (retention, deleted demo data): drop its row
        self.browse([m.id for m in existing.values()]).unlink()

    # ---- read API (for dashboards and vela_ai_agent) ------------------------------------

    @api.model
    def _freshness(self, dataset="real"):
        """Latest computation time and whether local metrics are stale (IN-04)."""
        latest = self.search([("dataset", "=", dataset), ("source", "=", "local")],
                             order="computed_at desc", limit=1).computed_at
        stale = not latest or fields.Datetime.now() - latest > M.STALE_AFTER
        return {"computed_at": latest, "stale": stale}


class VelaAnalyticsAlert(models.Model):
    """An anomaly found in the metrics, with the numbers that justify it (plan §9)."""

    _name = "vela.analytics.alert"
    _description = "Analytics Alert"
    _order = "window_start desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    alert_type = fields.Selection([
        ("checkout_error_spike", "Checkout error spike"),
        ("demand_spike", "Demand spike"),
        ("zero_result_search_spike", "Zero-result search spike"),
    ], required=True, readonly=True, index=True)
    severity = fields.Selection([("medium", "Medium"), ("high", "High")], readonly=True)
    window_start = fields.Datetime(required=True, readonly=True, index=True)
    window_end = fields.Datetime(readonly=True)
    segment = fields.Char(readonly=True, default="all")
    product_id = fields.Many2one("product.product", readonly=True, ondelete="set null")
    measured = fields.Float(readonly=True, digits=(16, 4))
    baseline = fields.Float(readonly=True, digits=(16, 4))
    threshold = fields.Float(readonly=True, digits=(16, 4))
    sample_size = fields.Integer(readonly=True)
    detection_rule = fields.Char(readonly=True)
    evidence = fields.Json(readonly=True)
    status = fields.Selection(
        [("new", "New"), ("acknowledged", "Acknowledged"), ("resolved", "Resolved")],
        default="new", required=True, index=True, readonly=True,
    )
    source = fields.Selection(SOURCES, required=True, default="local", readonly=True)
    dataset = fields.Selection(DATASETS, required=True, default="real", readonly=True, index=True)

    _alert_uniq = models.Constraint(
        "unique (alert_type, segment, window_start, source, dataset)",
        "One alert per type, segment, window, source and dataset.",
    )

    @api.depends("alert_type", "segment", "window_start")
    def _compute_name(self):
        labels = dict(self._fields["alert_type"].selection)
        for alert in self:
            seg = "" if alert.segment in (False, "all") else f" ({alert.segment})"
            alert.name = f"{labels.get(alert.alert_type, '')}{seg}"

    def action_acknowledge(self):
        self.filtered(lambda a: a.status == "new").write({"status": "acknowledged"})

    def action_resolve(self):
        self.write({"status": "resolved"})

    # ---- detection ----------------------------------------------------------------------

    @api.model
    def _detect(self, window_start, dataset):
        Metric = self.env["vela.analytics.metric"]
        t = Metric._thresholds()
        found = []
        current = Metric.search([("window_start", "=", window_start), ("source", "=", "local"),
                                 ("dataset", "=", dataset)])
        by_key = defaultdict(dict)
        for metric in current:
            by_key[metric.metric_key][metric.segment] = metric
        history = Metric.search([
            ("source", "=", "local"), ("dataset", "=", dataset),
            ("metric_key", "in", ["checkout_error_ratio", "add_to_cart", "search_zero_results"]),
            ("window_start", "<", window_start),
            ("window_start", ">=", window_start - M.BASELINE_WINDOWS * M.WINDOW)])
        past = defaultdict(list)
        for metric in history:
            past[(metric.metric_key, metric.segment)].append(metric)

        for segment, metric in by_key["checkout_error_ratio"].items():
            ratios = [m.value for m in past[("checkout_error_ratio", segment)] if m.denominator]
            if hit := M.checkout_error_rule(int(metric.numerator), int(metric.denominator),
                                            ratios, t):
                found.append(("checkout_error_spike", segment, metric, hit, {
                    "checkout_errors": int(metric.numerator),
                    "checkout_starts": int(metric.denominator),
                    "baseline_windows": len(ratios)}, False))
        for segment, metric in by_key["add_to_cart"].items():
            counts = [m.numerator for m in past[("add_to_cart", segment)]]
            if hit := M.demand_rule(int(metric.numerator), counts, t):
                sku = segment.split(":", 1)[1]
                product = self.env["vela.analytics.event"].search(
                    [("sku", "=", sku), ("product_id", "!=", False)], limit=1).product_id
                found.append(("demand_spike", segment, metric, hit, {
                    "add_to_cart": int(metric.numerator), "sku": sku,
                    "baseline_counts": counts}, product.id or False))
        if metric := by_key["search_zero_results"].get("all"):
            counts = [m.numerator for m in past[("search_zero_results", "all")]]
            if hit := M.zero_search_rule(int(metric.numerator), counts, t):
                found.append(("zero_result_search_spike", "all", metric, hit, {
                    "zero_result_searches": int(metric.numerator),
                    "baseline_counts": counts}, False))
        return self._upsert_alerts(window_start, dataset, found)

    @api.model
    def _upsert_alerts(self, window_start, dataset, found):
        """Recomputing a window refreshes an alert's numbers but keeps its status."""
        alerts = self.browse()
        for alert_type, segment, metric, hit, evidence, product_id in found:
            vals = {
                "severity": hit["severity"], "measured": hit["measured"],
                "baseline": hit["baseline"], "threshold": hit["threshold"],
                "sample_size": int(metric.denominator or metric.numerator),
                "detection_rule": hit["rule"], "product_id": product_id,
                "evidence": {**evidence, "window_start": window_start.isoformat() + "Z",
                             "metric_id": metric.id},
            }
            alert = self.search([("alert_type", "=", alert_type), ("segment", "=", segment),
                                 ("window_start", "=", window_start), ("source", "=", "local"),
                                 ("dataset", "=", dataset)], limit=1)
            if alert:
                alert.write(vals)
            else:
                alert = self.create({**vals, "alert_type": alert_type, "segment": segment,
                                     "window_start": window_start,
                                     "window_end": window_start + timedelta(minutes=5),
                                     "dataset": dataset, "source": "local"})
                _logger.info("vela_analytics: alert %s %s (%s)", alert_type, segment, dataset)
            alerts |= alert
        return alerts
