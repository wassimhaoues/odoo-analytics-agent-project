"""Fake Kafka bridge: the Odoo → bridge HTTP contract (tracking-contract.md "Bridge"),
without Kafka. Used by the tests, for manual end-to-end checks, and as the reference
behaviour for the real bridge in pipeline/.

    # inside the Odoo container (reachable from Odoo as http://localhost:8099)
    docker compose exec -d odoo python3 /mnt/extra-addons/vela_analytics/tests/fake_bridge.py \\
        --port 8099 --token dev --out /tmp/bridge.jsonl

Contract: POST /v1/events, Authorization: Bearer <token>, body {"events": [...]} (≤ 500).
200 {"results": [{"event_id", "status": accepted|duplicate|rejected, "error"}]}.
401 bad token · 400 bad body · 5xx = try again later.
"""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_EVENTS = 500
REQUIRED = ("v", "event_id", "event", "ts", "website_id", "is_synthetic")


def check_event(event):
    """Return an error string, or '' when the envelope is valid vela.events.v1."""
    if not isinstance(event, dict):
        return "event must be an object"
    missing = [k for k in REQUIRED if k not in event]
    if missing:
        return f"missing {missing}"
    if event["v"] != 1:
        return "unsupported version"
    if "session" not in event and event["event"] != "order_confirmed":
        return "session required"
    return ""


class FakeBridge:
    def __init__(self, port=0, token="", out=None):
        self.token, self.out = token, out
        self.fail_status = None  # e.g. 500 or 401: answer every batch with this status
        self.reject_ids = set()  # event_ids to answer "rejected"
        self.seen, self.received, self.batches = set(), [], 0
        self.running = False
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.port = self.server.server_address[1]
        self.url = f"http://localhost:{self.port}"

    def _handler(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self, status, body=None):
                data = json.dumps(body or {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                if self.path != "/v1/events":
                    return self._answer(404, {"error": "not found"})
                if bridge.fail_status:
                    return self._answer(bridge.fail_status, {"error": "simulated"})
                if bridge.token and self.headers.get("Authorization") != f"Bearer {bridge.token}":
                    return self._answer(401, {"error": "bad token"})
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    events = json.loads(self.rfile.read(length))["events"]
                    assert isinstance(events, list) and 0 < len(events) <= MAX_EVENTS
                except (ValueError, KeyError, TypeError, AssertionError):
                    return self._answer(400, {"error": "body must be {events: [1..500]}"})
                return self._answer(200, {"results": bridge.accept(events)})

        return Handler

    def accept(self, events):
        results = []
        with self.lock:
            self.batches += 1
            for event in events:
                event_id = str(event.get("event_id")) if isinstance(event, dict) else ""
                error = check_event(event) or ("rejected on request"
                                                if event_id in self.reject_ids else "")
                if error:
                    results.append({"event_id": event_id, "status": "rejected", "error": error})
                elif event_id in self.seen:
                    results.append({"event_id": event_id, "status": "duplicate"})
                else:
                    self.seen.add(event_id)
                    self.received.append(event)
                    if self.out:
                        with open(self.out, "a", encoding="utf-8") as fh:
                            fh.write(json.dumps(event) + "\n")
                    results.append({"event_id": event_id, "status": "accepted"})
        return results

    def start(self):
        self.running = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def stop(self):
        if self.running:  # shutdown() waits forever for a serve_forever() that never ran
            self.server.shutdown()
            self.running = False
        self.server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--token", default="")
    parser.add_argument("--out", help="append accepted events here as JSON lines")
    args = parser.parse_args()
    fake = FakeBridge(args.port, args.token, args.out)
    print(f"fake bridge on {fake.url}/v1/events", flush=True)
    fake.server.serve_forever()
