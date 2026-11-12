"""Bounded memory admission policy that protects completed source state."""


def admit(*, requested_bytes, available_bytes, completed_source_state=True):
    if requested_bytes < 0 or available_bytes < 0:
        raise ValueError("invalid_memory_request")
    if requested_bytes <= available_bytes:
        return {"action": "run", "source_state_preserved": completed_source_state}
    return {
        "action": "queue",
        "source_state_preserved": completed_source_state,
        "reason": "memory_pressure",
    }
