"""Hermi Cockpit Event Client – sends events to the cockpit backend."""

import json
import urllib.request
import urllib.error

COCKPIT_URL = "http://127.0.0.1:8000/events"


def send_event(
    message: str,
    type: str = "log",
    level: str = "info",
    source: str = "hermi",
    meta: dict | None = None,
) -> dict | None:
    """Send an event to Hermi Cockpit. Returns response dict or None on failure."""
    payload = {
        "type": type,
        "level": level,
        "source": source,
        "message": message,
    }
    if meta is not None:
        payload["meta"] = meta

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            COCKPIT_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"[EventClient] Failed to send event: {e}")
        return None
    except Exception as e:
        print(f"[EventClient] Unexpected error: {e}")
        return None
