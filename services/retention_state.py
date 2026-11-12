"""Recording retention state transitions for browser failure conditions."""

FAILURES = {"quota_exhausted", "storage_evicted", "microphone_removed"}


def transition(*, event, persisted_bytes=0):
    if event in FAILURES:
        return {
            "state": "retention_failed",
            "event": event,
            "retained": False,
            "persisted_bytes": persisted_bytes,
        }
    if event == "persisted":
        return {
            "state": "retained",
            "event": event,
            "retained": True,
            "persisted_bytes": persisted_bytes,
        }
    raise ValueError("unknown_retention_event")
