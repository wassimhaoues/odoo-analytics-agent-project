import uuid
from datetime import datetime, timedelta

from odoo.tests import BaseCase, tagged

from ..services import validation as V

NOW = datetime(2026, 11, 21, 12, 0, 0)


def ev(**kw):
    return {"v": 1, "event_id": str(uuid.uuid4()), "event": "click", "track": "hero.cta.shop_now",
            "ts": "2026-11-21T11:59:00.000Z", **kw}


@tagged("post_install", "-at_install", "vela")
class TestValidation(BaseCase):
    def ok(self, **kw):
        return V.validate_browser_event(ev(**kw), NOW, "localhost")

    def bad(self, raw):
        with self.assertRaises(V.InvalidEvent):
            V.validate_browser_event(raw, NOW, "localhost")

    def test_valid_click(self):
        vals = self.ok(product="VT-LAP-001", position=3, utm={"source": "Instagram"})
        self.assertEqual(vals["sku"], "VT-LAP-001")
        self.assertEqual(vals["source"], "instagram")
        self.assertEqual(vals["occurred_at"], NOW - timedelta(minutes=1))

    def test_rejects(self):
        self.bad(ev(event="order_confirmed"))  # IN-02: server only
        self.bad(ev(event="add_to_cart"))
        self.bad(ev(email="a@b.c"))  # unknown field
        self.bad(ev(v=2))
        self.bad(ev(event_id="not-a-uuid"))
        self.bad(ev(track="Bad Track"))
        self.bad(ev(track=None))  # click without track
        self.bad(ev(product="<script>"))
        self.bad(ev(position=0))
        self.bad(ev(position=True))
        self.bad(ev(page="/" + "x" * 3000))
        self.bad(ev(event="checkout_error", error_code="payment_error"))  # server-only code
        self.bad(ev(error_code="form_validation"))  # only on checkout_error
        self.bad(ev(utm={"source": "a b"}))
        self.bad("not a dict")

    def test_privacy(self):
        vals = self.ok(page="/shop?search=john@doe.com", ref="https://www.google.com/search?q=x")
        self.assertEqual(vals["page"], "/shop")
        self.assertEqual(vals["ref"], "www.google.com")
        self.assertIsNone(self.ok(ref="http://localhost/shop")["ref"])

    def test_clock_skew_clamped(self):
        self.assertEqual(self.ok(ts="2020-01-01T00:00:00Z")["occurred_at"], NOW)
        self.assertEqual(self.ok(ts="garbage")["occurred_at"], NOW)

    def test_identity(self):
        a = V.visitor_hash("salt", "token")
        self.assertEqual(len(a), 16)
        self.assertEqual(a, V.visitor_hash("salt", "token"))
        self.assertNotEqual(a, V.visitor_hash("other", "token"))
        self.assertNotIn("token", a)
        self.assertEqual(V.order_event_id("S00001"), V.order_event_id("S00001"))

    def test_device_and_bots(self):
        self.assertEqual(V.device_of("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"), "mobile")
        self.assertEqual(V.device_of("Mozilla/5.0 (iPad; CPU OS 17_0)"), "tablet")
        self.assertEqual(V.device_of("Mozilla/5.0 (X11; Linux x86_64)"), "desktop")
        self.assertTrue(V.is_bot("Googlebot/2.1"))
        self.assertTrue(V.is_bot(""))

    def test_rate_limiter(self):
        limiter = V.RateLimiter(limit=3, window=60)
        self.assertTrue(limiter.allow("k", cost=3, now=0))
        self.assertFalse(limiter.allow("k", now=1))
        self.assertTrue(limiter.allow("k", now=61))
