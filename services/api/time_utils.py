"""Shared UTC event time representation."""
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat()
