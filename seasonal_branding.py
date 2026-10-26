"""One-time Halloween 2026 branding window; all timestamps are UTC."""
from datetime import datetime, timezone

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)


def configuration(now=None):
    now = now or datetime.now(timezone.utc)
    return {
        "startsAt": int(START.timestamp() * 1000),
        "endsAt": int(END.timestamp() * 1000),
        "serverTime": int(now.timestamp() * 1000),
    }
