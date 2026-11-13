"""Nonblocking local process admission; not a distributed scheduler or memory quota."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4
from services.resource_arbiter import decide

MIN_FREE_MEMORY_RESERVE_BYTES = 2 * 1024**3
PRIORITY_MARKER_MAX_AGE_SECONDS = 24 * 60 * 60


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


def _priority_directory(lock_path):
    directory = lock_path.with_name(lock_path.name + ".priority")
    if directory.is_symlink():
        raise ValueError("inference_priority_directory_symlink")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _source_marker(lock_path):
    return _priority_directory(lock_path) / f"source-{os.getpid()}.json"


def _register_source_request(lock_path):
    marker = _source_marker(lock_path)
    temporary = marker.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "requested_epoch": time.time(),
            }
        ),
        encoding="utf-8",
    )
    os.replace(temporary, marker)
    return marker


def _clear_source_request(lock_path):
    try:
        _source_marker(lock_path).unlink(missing_ok=True)
    except OSError:
        pass


def _pid_is_running(pid):
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            return kernel32.WaitForSingleObject(handle, 0) == 0x102
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _source_request_pending(lock_path):
    directory = lock_path.with_name(lock_path.name + ".priority")
    if directory.is_symlink():
        return True
    if not directory.is_dir():
        return False
    pending = False
    now = time.time()
    for marker in directory.glob("source-*.json"):
        try:
            if marker.is_symlink():
                marker.unlink(missing_ok=True)
                continue
            row = json.loads(marker.read_text(encoding="utf-8"))
            pid, requested = row.get("pid"), row.get("requested_epoch")
            if (
                type(pid) is not int
                or type(requested) not in (int, float)
                or requested > now
                or now - requested > PRIORITY_MARKER_MAX_AGE_SECONDS
                or not _pid_is_running(pid)
            ):
                marker.unlink(missing_ok=True)
                continue
            pending = True
        except (OSError, ValueError, TypeError):
            try:
                marker.unlink(missing_ok=True)
            except OSError:
                pending = True
    return pending


@contextmanager
def local_inference_slot(requested_bytes=2 * 1024**3, *, priority="optional"):
    if priority not in {"optional", "source"}:
        raise ValueError("invalid_inference_priority")
    path = Path(
        os.environ.get("MED_TRANSCRIPT_INFERENCE_LOCK", "data/local-inference.lock")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    source_marker = _register_source_request(path) if priority == "source" else None
    if priority == "optional" and _source_request_pending(path):
        yield False
        return
    acquired = False
    admitted = False
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
            if acquired and not (
                priority == "optional" and _source_request_pending(path)
            ):
                admitted = memory_admission(requested_bytes)["status"] == "admit"
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
            if source_marker is not None and acquired:
                source_marker.unlink(missing_ok=True)
