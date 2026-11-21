import json
import logging
from urllib.parse import urlsplit

from odoo import fields, http
from odoo.http import request

from ..services import validation as V

_logger = logging.getLogger(__name__)


class VelaAnalyticsEvents(http.Controller):
    @http.route(
        "/vela/analytics/events", type="http", auth="public", methods=["POST"],
        csrf=False,  # sendBeacon can't carry a CSRF token; writes analytics only (security.md)
        website=True, sitemap=False, save_session=False,
    )
    def collect(self, **_kw):
        """Browser batch intake (plan §6). Always 204: tracking can never break the site."""
        try:
            self._collect()
        except Exception:  # noqa: BLE001 - never surface an error page to visitors
            _logger.exception("vela_analytics: event batch failed")
        return request.make_response("", status=204)

    def _collect(self):
        http_req = request.httprequest
        if (http_req.content_length or 0) > V.MAX_BODY_BYTES:
            return
        raw = http_req.get_data(cache=False)
        if len(raw) > V.MAX_BODY_BYTES:
            return
        Event = request.env["vela.analytics.event"]
        ctx = Event._request_context()
        if not ctx or not ctx["consent"] or ctx["bot"]:
            return  # T2: no consent, no browser events (the server re-checks the cookie)
        try:
            batch = json.loads(raw).get("events")
        except (ValueError, AttributeError):
            return
        if not isinstance(batch, list) or not batch or len(batch) > V.MAX_BATCH:
            return
        key = ctx["session"] or http_req.remote_addr
        if not V.RATE_LIMITER.allow(key, cost=len(batch)):
            _logger.info("vela_analytics: rate limit hit, %s events dropped", len(batch))
            return
        now = fields.Datetime.now()
        own_host = urlsplit(http_req.host_url).hostname
        trusted = {k: ctx[k] for k in ("website_id", "device", "consent", "session", "visitor")}
        clean, dropped = [], 0
        for raw_event in batch:
            try:
                vals = V.validate_browser_event(raw_event, now, own_host)
            except V.InvalidEvent:
                dropped += 1
                continue
            clean.append({**vals, **trusted, "origin": "browser", "received_at": now})
        if dropped:
            _logger.info("vela_analytics: %s invalid events dropped", dropped)
        if clean:
            Event.sudo()._record(clean)  # sudo: public visitor, values validated above
