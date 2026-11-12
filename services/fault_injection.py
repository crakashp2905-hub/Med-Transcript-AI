"""Deterministic fault-injection outcomes for worker safety tests."""

FAULTS = {"slow_disk", "write_failure", "process_kill", "database_busy", "model_absent"}


def inject(fault):
    if fault not in FAULTS:
        raise ValueError("unknown_fault")
    return {
        "fault": fault,
        "retryable": fault in {"slow_disk", "database_busy"},
        "source_state_preserved": True,
        "publication_allowed": False,
    }
