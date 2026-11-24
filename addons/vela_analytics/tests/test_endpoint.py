import json
import uuid

from odoo.tests import HttpCase, tagged

from ..services import validation as V

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
URL = "/vela/analytics/events"


def ev(**kw):
    return {"v": 1, "event_id": str(uuid.uuid4()), "event": "page_view", "page": "/shop",
            "ts": "2026-11-21T11:59:00.000Z", **kw}


@tagged("post_install", "-at_install", "vela")
class TestEndpoint(HttpCase):
    def setUp(self):
        super().setUp()
        V.RATE_LIMITER.hits.clear()
        self.Event = self.env["vela.analytics.event"]
        self.session = str(uuid.uuid4())

    def consent(self, optional=True):
        self.opener.cookies.set("website_cookies_bar",
                                json.dumps({"required": True, "optional": optional}))
        self.opener.cookies.set("vela_session", self.session)

    def post(self, events=None, body=None, ua=UA):
        data = body if body is not None else json.dumps({"events": events})
        res = self.url_open(URL, data=data, headers={"Content-Type": "application/json",
                                                     "User-Agent": ua})
        self.assertEqual(res.status_code, 204)
        return self.Event.search([("session", "=", self.session)])

    def test_no_consent_no_events(self):  # T2
        self.post([ev()])
        self.consent(optional=False)
        self.assertFalse(self.post([ev()]))
        self.assertFalse(self.Event.search([("page", "=", "/shop"), ("origin", "=", "browser")]))

    def test_consent_stores_with_trusted_fields(self):  # T2
        self.consent()
        click = ev(event="click", track="product.add_to_cart", product="VT-LAP-001", position=2)
        events = self.post([ev(), click])
        self.assertEqual(len(events), 2)
        stored = events.filtered(lambda e: e.event == "click")
        self.assertEqual(stored.track, "product.add_to_cart")
        self.assertEqual(stored.device, "desktop")
        self.assertTrue(stored.consent)
        self.assertEqual(len(stored.visitor), 16)
        self.assertEqual(stored.outbox_ids.state, "pending")  # FR-03

    def test_duplicates_skipped(self):
        self.consent()
        same = ev()
        self.post([same, same])
        self.assertEqual(len(self.post([same])), 1)

    def test_bad_input_dropped_site_unaffected(self):
        self.consent()
        self.post(body="not json")
        self.post(body=json.dumps({"events": [ev()] * 51}))
        self.post(body=json.dumps({"events": [ev(page="/" + "x" * 40_000)]}))
        self.post([ev(event="order_confirmed")])  # IN-02
        self.assertFalse(self.post([ev()], ua="Googlebot/2.1"))
        self.assertEqual(len(self.post([ev(), ev(track="BAD!", event="click")])), 1)

    def test_rate_limit(self):
        self.consent()
        for _ in range(V.RATE_LIMIT_PER_MIN // 40):
            self.post([ev() for _ in range(40)])
        self.assertEqual(len(self.post([ev()])), V.RATE_LIMIT_PER_MIN)
