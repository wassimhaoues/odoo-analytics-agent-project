from datetime import timedelta

from odoo import api, fields, models

SENT_RETENTION_DAYS = 7


class VelaAnalyticsOutbox(models.Model):
    """One row per event to deliver to the Kafka bridge (FR-03, plan §8).

    Phase A only creates rows; the sending cron comes in phase B.
    """

    _name = "vela.analytics.outbox"
    _description = "Analytics Outbox"
    _order = "id"
    _rec_name = "event_id"

    event_ref_id = fields.Many2one(
        "vela.analytics.event", "Event", required=True, readonly=True, ondelete="cascade",
    )
    event_id = fields.Char(related="event_ref_id.event_id", string="Event ID")
    event = fields.Selection(related="event_ref_id.event", string="Event type")
    is_synthetic = fields.Boolean(related="event_ref_id.is_synthetic")
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("dead", "Dead")],
        default="pending", required=True, index=True, readonly=True,
    )
    attempts = fields.Integer(readonly=True)
    last_error = fields.Char(readonly=True)
    next_retry_at = fields.Datetime(default=fields.Datetime.now, index=True, readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _event_uniq = models.Constraint("unique (event_ref_id)", "One outbox row per event.")

    @api.model
    def _cron_retention(self, days=SENT_RETENTION_DAYS):
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([("state", "=", "sent"), ("sent_at", "<", cutoff)], limit=10_000)
        old.unlink()
        return len(old)
