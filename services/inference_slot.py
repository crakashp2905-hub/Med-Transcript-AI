"""Nonblocking local process admission; not a distributed scheduler or memory quota."""
from contextlib import contextmanager
import os
from pathlib import Path


@contextmanager
def local_inference_slot():
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
        try:yield acquired
        finally:
            if acquired:
                if os.name=='nt':
                    import msvcrt
                    handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_UN)
