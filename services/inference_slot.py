"""Nonblocking local process admission; not a distributed scheduler or memory quota."""

from contextlib import contextmanager
import os
from pathlib import Path
from services.resource_arbiter import decide

MIN_FREE_MEMORY_RESERVE_BYTES = 2 * 1024**3


def available_memory_bytes():
    """OS available physical memory; return zero when it cannot be measured."""
    try:
        if os.name == "nt":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("length", ctypes.c_ulong),
                    ("load", ctypes.c_ulong),
                    *[
                        (name, ctypes.c_ulonglong)
                        for name in (
                            "total",
                            "available",
                            "page_total",
                            "page_available",
                            "virtual_total",
                            "virtual_available",
                            "extended",
                        )
                    ],
                ]

            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return 0
            return status.available
        values = dict(
            line.split(":", 1)
            for line in Path("/proc/meminfo").read_text().splitlines()
        )
        return int(values["MemAvailable"].split()[0]) * 1024
    except (OSError, ValueError, KeyError, AttributeError):
        return 0


def admission_capacity_bytes(available_bytes=None, configured_bytes=None):
    """Return usable inference headroom after retaining a fixed OS reserve."""
    available = available_memory_bytes() if available_bytes is None else available_bytes
    if type(available) is not int or available < 0:
        raise ValueError("invalid_available_memory")
    if configured_bytes is None:
        configured = os.environ.get("MED_TRANSCRIPT_LOCAL_MEMORY_BYTES")
        configured_bytes = int(configured) if configured is not None else available
    if type(configured_bytes) is not int or configured_bytes < 0:
        raise ValueError("invalid_local_memory_budget")
    return max(0, min(available, configured_bytes) - MIN_FREE_MEMORY_RESERVE_BYTES)


def memory_request_fits(requested_bytes):
    """Check a model estimate against current usable headroom, fail closed."""
    return memory_admission(requested_bytes)["status"] == "admit"


def memory_admission(requested_bytes):
    """Return a safe audit receipt for a serialized local inference request."""
    if type(requested_bytes) is not int or requested_bytes < 0:
        raise ValueError("invalid_memory_request")
    available = available_memory_bytes()
    configured = os.environ.get("MED_TRANSCRIPT_LOCAL_MEMORY_BYTES")
    try:
        configured_bytes = int(configured) if configured is not None else available
    except ValueError:
        configured_bytes = 0
    capacity = admission_capacity_bytes(available, configured_bytes)
    decision = decide(
        active_bytes=0,
        request_bytes=requested_bytes,
        capacity_bytes=capacity,
    )
    return {
        "status": "admit" if decision["action"] == "admit" else "defer",
        "requested_bytes": requested_bytes,
        "available_bytes_at_check": available,
        "reserved_free_bytes": MIN_FREE_MEMORY_RESERVE_BYTES,
        "admission_capacity_bytes": capacity,
        "reason": decision.get("reason"),
        "configured_memory_cap": configured is not None,
    }


def estimate_model_request_bytes(artifact_paths):
    """Conservative ASR estimate: 2x artifact bytes plus 512 MiB runtime overhead."""
    paths = list(artifact_paths)
    if not paths:
        raise ValueError("model_artifacts_required")
    total = 0
    for item in paths:
        path = Path(item)
        if path.is_symlink() or not path.is_file():
            raise ValueError("model_artifact_unavailable")
        total += path.stat().st_size
    return total * 2 + 512 * 1024**2


@contextmanager
def local_inference_slot(requested_bytes=2 * 1024**3):
    path = Path(
        os.environ.get("MED_TRANSCRIPT_INFERENCE_LOCK", "data/local-inference.lock")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    acquired = False
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except (BlockingIOError, PermissionError):
            pass
        try:
            # The shared file lock serializes ASR and Qwen processes, so under
            # this lock no competing admitted request has an active reservation.
            admitted = (
                acquired and memory_admission(requested_bytes)["status"] == "admit"
            )
            yield admitted
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle, fcntl.LOCK_UN)
