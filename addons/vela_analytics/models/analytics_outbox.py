import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools import SQL

from ..services import delivery

_logger = logging.getLogger(__name__)

SENT_RETENTION_DAYS = 7
BATCH_SIZE = 500
MAX_ATTEMPTS = 20
MAX_BACKOFF_MINUTES = 60
MAX_BATCHES_PER_RUN = 20


class VelaAnalyticsOutbox(models.Model):
    """One row per event to deliver to the Kafka bridge (FR-03, plan §8).

    At-least-once: a row is marked sent only after the bridge acknowledged its event_id;
    consumers deduplicate on event_id.
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
    channel = fields.Selection(
        [("local", "Local only"), ("bridge", "Kafka bridge")], readonly=True,
        help="Local only: Kafka delivery was off (VELA_DELIVERY_MODE=local) when processed.",
    )
    attempts = fields.Integer(readonly=True)
    last_error = fields.Char(readonly=True)
    next_retry_at = fields.Datetime(default=fields.Datetime.now, index=True, readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _event_uniq = models.Constraint("unique (event_ref_id)", "One outbox row per event.")

    # ---- delivery -----------------------------------------------------------------------

    @api.model
    def _cron_deliver(self):
        """Every minute: deliver due rows in batches, committing after each batch."""
        cron = self.env["ir.cron"]
        for _ in range(MAX_BATCHES_PER_RUN):
            done = self._deliver_batch()
            if not done or cron._commit_progress(done) <= 0:
                break

    @api.model
    def _due_rows(self, limit=BATCH_SIZE):
        # raw SQL below: write pending ORM changes (state, backoff dates) first
        self.flush_model(["state", "next_retry_at"])
        # SKIP LOCKED: two workers (or a manual run) never send the same row twice at once
        self.env.cr.execute(SQL(
            """SELECT id FROM vela_analytics_outbox
                WHERE state IN ('pending', 'failed') AND next_retry_at <= %s
                ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED""",
            fields.Datetime.now(), limit,
        ))
        return self.browse([row[0] for row in self.env.cr.fetchall()])

    @api.model
    def _deliver_batch(self, limit=BATCH_SIZE):
        """Deliver one batch of due rows. Returns how many rows were processed."""
        rows = self._due_rows(limit)
        if not rows:
            return 0
        mode, url, token = delivery.config()
        now = fields.Datetime.now()
        if mode == "local":
            rows.write({"state": "sent", "channel": "local", "sent_at": now, "last_error": False})
            return len(rows)
        by_event_id = {row.event_ref_id.event_id: row for row in rows}
        envelopes = [row.event_ref_id._to_envelope() for row in rows]
        try:
            results = delivery.post_batch(url, token, envelopes)
        except delivery.BridgeError as exc:
            level = logging.WARNING if exc.retry else logging.ERROR
            _logger.log(level, "vela_analytics: %s rows not delivered: %s", len(rows), exc)
            rows._schedule_retry(str(exc))
            return len(rows)
        sent = self.browse()
        missing = self.browse()
        for event_id, row in by_event_id.items():
            status, error = results.get(event_id, (None, ""))
            if status in ("accepted", "duplicate"):
                sent |= row
            elif status == "rejected":
                row.write({"state": "dead", "attempts": row.attempts + 1,
                           "last_error": f"rejected by bridge: {error}"[:500]})
                _logger.error("vela_analytics: event %s rejected: %s", event_id, error)
            else:
                missing |= row
        sent.write({"state": "sent", "channel": "bridge", "sent_at": now, "last_error": False})
        missing._schedule_retry("no result for this event in the bridge answer")
        return len(rows)

    def _schedule_retry(self, error):
        now = fields.Datetime.now()
        groups = {}  # one write per attempt count, not per row; grouped before any write
        for row in self:
            groups[row.attempts] = groups.get(row.attempts, self.browse()) | row
        for previous, rows in groups.items():
            attempts = previous + 1
            delay = min(2 ** attempts, MAX_BACKOFF_MINUTES)
            rows.write({
                "attempts": attempts,
                "state": "dead" if attempts >= MAX_ATTEMPTS else "failed",
                "last_error": error[:500],
                "next_retry_at": now + timedelta(minutes=delay),
            })

    def action_retry(self):
        """Manager button: send failed/dead rows again at the next cron run."""
        self.filtered(lambda r: r.state in ("failed", "dead")).write({
            "state": "pending", "attempts": 0, "next_retry_at": fields.Datetime.now(),
        })

    # ---- retention ----------------------------------------------------------------------

    @api.model
    def _cron_retention(self, days=SENT_RETENTION_DAYS):
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([("state", "=", "sent"), ("sent_at", "<", cutoff)], limit=10_000)
        old.unlink()
        return len(old)
