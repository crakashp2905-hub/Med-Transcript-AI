"""Nonblocking local process admission; not a distributed scheduler or memory quota."""
from contextlib import contextmanager
import os
from pathlib import Path
from services.resource_arbiter import decide


def available_memory_bytes():
    """OS available physical memory; return zero when it cannot be measured."""
    try:
        if os.name == 'nt':
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in
                              ('total', 'available', 'page_total', 'page_available',
                               'virtual_total', 'virtual_available', 'extended')]]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return 0
            return status.available
        values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        return int(values['MemAvailable'].split()[0]) * 1024
    except (OSError, ValueError, KeyError, AttributeError):
        return 0


@contextmanager
def local_inference_slot(requested_bytes=2 * 1024**3):
    path=Path(os.environ.get('MED_TRANSCRIPT_INFERENCE_LOCK','data/local-inference.lock'))
    path.parent.mkdir(parents=True,exist_ok=True)
    acquired=False
    with path.open('a+b') as handle:
        handle.seek(0,2)
        if not handle.tell():handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            acquired=True
        except (BlockingIOError,PermissionError):pass
        try:
            available = available_memory_bytes()
            configured = os.environ.get('MED_TRANSCRIPT_LOCAL_MEMORY_BYTES')
            capacity = min(available, int(configured)) if configured else available
            # The shared file lock serializes ASR and Qwen processes, so under
            # this lock no competing admitted request has an active reservation.
            admitted = acquired and decide(active_bytes=0, request_bytes=requested_bytes,
                                          capacity_bytes=capacity)['action'] == 'admit'
            yield admitted
        finally:
            if acquired:
                if os.name=='nt':
                    import msvcrt
                    handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_UN)
