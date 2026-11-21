import logging
import secrets
import uuid
from datetime import timedelta

from odoo import api, fields, models
from odoo.http import request

from ..services import validation as V

_logger = logging.getLogger(__name__)

SALT_KEY = "vela_analytics.visitor_salt"
SESSION_COOKIE = "vela_session"
RETENTION_DAYS = 90


class VelaAnalyticsEvent(models.Model):
    _name = "vela.analytics.event"
    _description = "Analytics Event (vela.events.v1)"
    _order = "occurred_at desc, id desc"
    _rec_name = "event_id"

    event_id = fields.Char("Event ID", required=True, readonly=True)
    v = fields.Integer(default=V.SCHEMA_VERSION, readonly=True)
    event = fields.Selection(V.EVENT_TYPES, required=True, readonly=True, index=True)
    track = fields.Char(readonly=True)
    occurred_at = fields.Datetime(required=True, readonly=True, index=True)
    received_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    session = fields.Char(readonly=True, index=True)
    visitor = fields.Char(readonly=True, help="Salted hash of the Odoo visitor token.")
    website_id = fields.Many2one("website", readonly=True, ondelete="cascade")
    sku = fields.Char("SKU", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True, ondelete="set null")
    category = fields.Char(readonly=True)
    position = fields.Integer(readonly=True)
    quantity = fields.Integer(readonly=True)
    search_results_count = fields.Integer(readonly=True)
    error_code = fields.Selection(V.ERROR_CODES, readonly=True)
    page = fields.Char(readonly=True)
    ref = fields.Char("Referrer host", readonly=True)
    device = fields.Selection(
        [("mobile", "Mobile"), ("tablet", "Tablet"), ("desktop", "Desktop")], readonly=True
    )
    source = fields.Char(readonly=True)
    sale_order_id = fields.Many2one("sale.order", readonly=True, ondelete="set null")
    consent = fields.Boolean(readonly=True)
    is_synthetic = fields.Boolean(readonly=True, index=True)
    origin = fields.Selection(
        [("browser", "Browser"), ("server", "Server"), ("demo", "Demo")],
        required=True, readonly=True,
    )
    payload = fields.Json(readonly=True)
    outbox_ids = fields.One2many("vela.analytics.outbox", "event_ref_id", readonly=True)

    _event_id_uniq = models.Constraint("unique (event_id)", "Event ids must be unique.")

    # ---- identity & consent -------------------------------------------------------------

    @api.model
    def _visitor_salt(self):
        params = self.env["ir.config_parameter"].sudo()
        salt = params.get_str(SALT_KEY)
        if not salt:
            salt = secrets.token_hex(32)
            params.set_str(SALT_KEY, salt)
        return salt

    @api.model
    def _request_context(self):
        """Trusted, server-derived fields for the current request (plan §4).

        Without consent: no session, no visitor. Returns None outside a website request.
        """
        if not request or not request.env:
            return None
        website = self.env.website
        if not website:
            return None
        user_agent = request.httprequest.user_agent.string or ""
        consent = bool(request.env["ir.http"]._is_allowed_cookie("optional"))
        ctx = {
            "website_id": website.id,
            "device": V.device_of(user_agent),
            "consent": consent,
            "bot": V.is_bot(user_agent),
            "session": None,
            "visitor": None,
        }
        if consent:
            session = request.httprequest.cookies.get(SESSION_COOKIE)
            ctx["session"] = session if V.is_uuid(session) else None
            visitor = request.env["website.visitor"]._get_access_token()
            ctx["visitor"] = V.visitor_hash(self._visitor_salt(), visitor)
        return ctx

    # ---- writing ------------------------------------------------------------------------

    @api.model
    def _record(self, vals_list):
        """Create events + their outbox rows; existing event ids are skipped (dedup).

        Callers pass already-validated values and call this with sudo() at the trust boundary.
        """
        ids = [v["event_id"] for v in vals_list]
        known = set(self.search([("event_id", "in", ids)]).mapped("event_id"))
        fresh, seen = [], set()
        skus = {v["sku"] for v in vals_list if v.get("sku")}
        products = {}
        if skus:
            for product in self.env["product.product"].search([("default_code", "in", list(skus))]):
                products[product.default_code] = product.id
        for vals in vals_list:
            if vals["event_id"] in known or vals["event_id"] in seen:
                continue
            seen.add(vals["event_id"])
            if vals.get("sku") and not vals.get("product_id"):
                vals["product_id"] = products.get(vals["sku"])
            fresh.append(vals)
        events = self.create(fresh)
        self.env["vela.analytics.outbox"].create([{"event_ref_id": e.id} for e in events])
        return events

    @api.model
    def _emit_server(self, event, own_cursor=False, **vals):
        """Record one trusted server event for the current request.

        Never raises: tracking must not break carts, payments or orders (T6, IN-03).
        Without consent nothing is recorded (D2); order_confirmed has its own path.
        own_cursor: commit on a separate cursor, for errors whose transaction rolls back.
        """
        try:
            ctx = self._request_context()
            if not ctx or not ctx["consent"] or ctx["bot"]:
                return self.browse()
            now = fields.Datetime.now()
            http_req = request.httprequest
            # RPC/form posts: the visitor's page is the referrer, not the endpoint path
            page = http_req.referrer if http_req.method == "POST" else http_req.path
            values = {
                "event_id": str(uuid.uuid4()),
                "event": event,
                "occurred_at": now,
                "origin": "server",
                "page": V.path_only(page),
                **{k: ctx[k] for k in ("website_id", "device", "consent", "session", "visitor")},
                **vals,
            }
            if own_cursor:
                with self.env.registry.cursor() as cr:
                    # sudo: public visitor, server-built values
                    self.env(cr=cr, su=True)[self._name]._record([values])
                return self.browse()
            with self.env.cr.savepoint():
                return self.sudo()._record([values])  # sudo: public visitor, server-built values
        except Exception:  # noqa: BLE001 - tracking is best effort by design
            _logger.exception("vela_analytics: could not record %s", event)
            return self.browse()

    @api.model
    def _sku_of(self, product):
        """Same SKU as the theme's data-vela-sku: the template code for multi-variant products,
        so product_view, clicks and add_to_cart join on one key (tracking-contract.md)."""
        product = product.sudo()
        if not product:
            return False, None
        tmpl = product.product_tmpl_id
        if tmpl.product_variant_count > 1:
            sku = (tmpl.product_variant_ids[:1].default_code or "").rsplit("-", 1)[0]
            return sku or False, product.default_code or None
        return product.default_code or False, None

    # ---- export -------------------------------------------------------------------------

    def _to_envelope(self):
        """vela.events.v1 JSON for Kafka (tracking-contract.md)."""
        self.ensure_one()
        data = {
            "v": self.v,
            "event_id": self.event_id,
            "event": self.event,
            "track": self.track or None,
            "ts": self.occurred_at.isoformat(timespec="milliseconds") + "Z",
            "visitor": self.visitor or None,
            "session": self.session or None,
            "website_id": self.website_id.id,
            "page": self.page or None,
            "ref": self.ref or None,
            "product": self.sku or None,
            "category": self.category or None,
            "position": self.position or None,
            "quantity": self.quantity or None,
            "search_results_count": self.search_results_count if self.event == "search" else None,
            "error_code": self.error_code or None,
            "device": self.device or None,
            "source": self.source or None,
            "is_synthetic": self.is_synthetic,
            "origin": self.origin,
            **(self.payload or {}),
        }
        return {k: v for k, v in data.items() if v is not None}

    # ---- retention ----------------------------------------------------------------------

    @api.model
    def _cron_retention(self, days=RETENTION_DAYS):
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.search([("occurred_at", "<", cutoff)], limit=10_000)
        old.unlink()
        return len(old)
