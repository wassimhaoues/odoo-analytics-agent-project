"""Validation and request context for vela.events.v1 (plan §4, §6).

Pure functions where possible, so they are easy to test. Everything a browser sends is
untrusted: unknown fields, bad enums or oversized values reject the event.
"""
import hashlib
import hmac
import re
import time
import uuid
from collections import deque
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
MAX_BODY_BYTES = 32 * 1024
MAX_BATCH = 50
RATE_LIMIT_PER_MIN = 120
MAX_CLOCK_SKEW = timedelta(hours=24)

EVENT_TYPES = [
    ("page_view", "Page view"),
    ("product_view", "Product view"),
    ("click", "Click"),
    ("search", "Search"),
    ("add_to_cart", "Add to cart"),
    ("checkout_started", "Checkout started"),
    ("checkout_error", "Checkout error"),
    ("order_confirmed", "Order confirmed"),
]
BROWSER_EVENTS = {"page_view", "product_view", "click", "checkout_started", "checkout_error"}
ERROR_CODES = [
    ("address_invalid", "Address invalid"),
    ("delivery_unavailable", "Delivery unavailable"),
    ("out_of_stock", "Out of stock"),
    ("payment_error", "Payment error"),
    ("payment_rejected", "Payment rejected"),
    ("server_error", "Server error"),
    ("form_validation", "Form validation"),
]
BROWSER_ERROR_CODES = {"form_validation"}

TRACK_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+){1,4}$")
SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,40}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
FIELD_RE = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
VIEWPORT_RE = re.compile(r"^\d{2,5}x\d{2,5}$")
BOT_RE = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|monitor", re.I)
TABLET_RE = re.compile(r"ipad|tablet|kindle|silk", re.I)
MOBILE_RE = re.compile(r"mobi|android|iphone", re.I)

ALLOWED_FIELDS = {"v", "event_id", "event", "track", "ts", "session", "page", "ref", "product",
                  "category", "position", "viewport", "utm", "error_code", "field"}


class InvalidEvent(ValueError):
    """A browser event that must be dropped."""


def is_uuid(value):
    return isinstance(value, str) and bool(UUID_RE.match(value))


def _short(value, limit):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise InvalidEvent("string too long or not a string")
    return value


def _int(value, low=0, high=10_000):
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise InvalidEvent("integer out of range")
    return value


def parse_ts(value, now):
    """Browser time, clamped: too far from server time → server time."""
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return now
    return ts if abs(ts - now) <= MAX_CLOCK_SKEW else now


def path_only(url, limit=512):
    """Keep the path, never the query string (it may carry personal data)."""
    if not url:
        return None
    path = urlsplit(str(url)).path or "/"
    return path[:limit]


def ref_host(url, own_host):
    if not url:
        return None
    host = (urlsplit(str(url)).hostname or "")[:255]
    return None if not host or host == own_host else host


def clean_utm(utm):
    if utm is None:
        return None
    if not isinstance(utm, dict):
        raise InvalidEvent("utm must be an object")
    out = {}
    for key in ("source", "medium", "campaign"):
        val = utm.get(key)
        if val:
            val = str(val).lower()[:64]
            if not SLUG_RE.match(val):
                raise InvalidEvent("bad utm value")
            out[key] = val
    return out or None


def validate_browser_event(raw, now, own_host):
    """Return clean field values for one browser event, or raise InvalidEvent."""
    if not isinstance(raw, dict):
        raise InvalidEvent("event must be an object")
    unknown = set(raw) - ALLOWED_FIELDS
    if unknown:
        raise InvalidEvent(f"unknown fields: {sorted(unknown)}")
    if raw.get("v") != SCHEMA_VERSION:
        raise InvalidEvent("unsupported version")
    if not is_uuid(raw.get("event_id")):
        raise InvalidEvent("event_id must be a UUID")
    event = raw.get("event")
    if event not in BROWSER_EVENTS:  # order_confirmed & co. only come from the server (IN-02)
        raise InvalidEvent("event not allowed from the browser")
    track = _short(raw.get("track"), 120)
    if track and not TRACK_RE.match(track):
        raise InvalidEvent("bad track id")
    if event == "click" and not track:
        raise InvalidEvent("click without track id")
    product = _short(raw.get("product"), 41)
    if product and not SKU_RE.match(product):
        raise InvalidEvent("bad SKU")
    category = _short(raw.get("category"), 64)
    if category and not SLUG_RE.match(category):
        raise InvalidEvent("bad category")
    error_code = raw.get("error_code")
    if event == "checkout_error":
        if error_code not in BROWSER_ERROR_CODES:
            raise InvalidEvent("bad error_code")
    elif error_code:
        raise InvalidEvent("error_code only on checkout_error")
    field = _short(raw.get("field"), 41)
    if field and not FIELD_RE.match(field):
        raise InvalidEvent("bad field name")
    viewport = _short(raw.get("viewport"), 11)
    if viewport and not VIEWPORT_RE.match(viewport):
        raise InvalidEvent("bad viewport")
    utm = clean_utm(raw.get("utm"))
    payload = {k: v for k, v in (("utm", utm), ("viewport", viewport), ("field", field)) if v}
    return {
        "event_id": raw["event_id"],
        "event": event,
        "track": track,
        "occurred_at": parse_ts(raw.get("ts"), now),
        "page": path_only(_short(raw.get("page"), 2048)),
        "ref": ref_host(_short(raw.get("ref"), 2048), own_host),
        "sku": product,
        "category": category,
        "position": _int(raw.get("position"), 1, 1000),
        "error_code": error_code if event == "checkout_error" else False,
        "source": (utm or {}).get("source"),
        "payload": payload or None,
    }


def device_of(user_agent):
    ua = user_agent or ""
    if TABLET_RE.search(ua):
        return "tablet"
    if MOBILE_RE.search(ua):
        return "mobile"
    return "desktop"


def is_bot(user_agent):
    return not user_agent or bool(BOT_RE.search(user_agent))


def visitor_hash(salt, access_token):
    """Pseudonymous, stable visitor id: the real Odoo token never leaves Odoo (plan §4)."""
    if not access_token:
        return None
    digest = hmac.new(salt.encode(), str(access_token).encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def order_event_id(order_name):
    """Deterministic id: confirming the same order twice can't create two events."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"vela:order_confirmed:{order_name}"))


class RateLimiter:
    """Best-effort sliding window per key, per worker process (plan §6)."""

    def __init__(self, limit=RATE_LIMIT_PER_MIN, window=60.0, max_keys=10_000):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.hits = {}

    def allow(self, key, cost=1, now=None):
        now = time.monotonic() if now is None else now
        if len(self.hits) > self.max_keys:
            self.hits.clear()
        q = self.hits.setdefault(key, deque())
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) + cost > self.limit:
            return False
        q.extend([now] * cost)
        return True


RATE_LIMITER = RateLimiter()
