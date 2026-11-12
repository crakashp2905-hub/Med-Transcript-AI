"""Shared memory arbiter for competing local ASR and drafting requests."""


def decide(*, active_bytes, request_bytes, capacity_bytes):
    if min(active_bytes, request_bytes, capacity_bytes) < 0:
        raise ValueError("invalid_memory_values")
    if active_bytes + request_bytes <= capacity_bytes:
        return {"action": "admit", "oversubscribed": False}
    return {"action": "defer", "oversubscribed": True, "reason": "memory_capacity"}
