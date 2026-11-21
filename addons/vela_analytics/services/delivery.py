"""Client for the Odoo → Kafka HTTP bridge (plan §8, tracking-contract.md "Bridge").

Config comes from the container environment (.env → docker-compose), never from git or
the database, so the token stays out of backups:

  VELA_DELIVERY_MODE   local (default: no network, rows marked sent) | bridge
  VELA_BRIDGE_URL      e.g. http://bridge:8000  (POST {url}/v1/events)
  VELA_BRIDGE_TOKEN    bearer token shared with the bridge
"""
import os

import requests

TIMEOUT = 10
RESULT_STATUSES = {"accepted", "duplicate", "rejected"}


class BridgeError(Exception):
    """The whole batch failed. retry=False means a contract/config error (4xx)."""

    def __init__(self, message, retry=True):
        super().__init__(message)
        self.retry = retry


def config():
    mode = (os.environ.get("VELA_DELIVERY_MODE") or "local").strip().lower()
    url = (os.environ.get("VELA_BRIDGE_URL") or "").strip().rstrip("/")
    token = (os.environ.get("VELA_BRIDGE_TOKEN") or "").strip()
    if mode not in ("local", "bridge"):
        mode = "local"
    return mode, url, token


def post_batch(url, token, envelopes, timeout=TIMEOUT):
    """POST one batch. Returns {event_id: (status, error)}; raises BridgeError."""
    if not url:
        raise BridgeError("VELA_BRIDGE_URL is not set", retry=False)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.post(f"{url}/v1/events", json={"events": envelopes},
                             headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise BridgeError(f"bridge unreachable: {type(exc).__name__}") from exc
    if resp.status_code >= 500:
        raise BridgeError(f"bridge error {resp.status_code}")
    if resp.status_code != 200:
        raise BridgeError(f"bridge refused batch: {resp.status_code} {resp.text[:200]}",
                          retry=False)
    try:
        results = resp.json()["results"]
        out = {}
        for item in results:
            status = item["status"]
            if status not in RESULT_STATUSES:
                raise ValueError(status)
            out[str(item["event_id"])] = (status, str(item.get("error") or "")[:500])
    except (ValueError, KeyError, TypeError) as exc:
        raise BridgeError("bridge answered with an invalid body", retry=False) from exc
    return out
