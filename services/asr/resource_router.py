"""Single-heavyweight-backend process pool with explicit fail-closed capacity."""

import threading

from services.asr.backend import BackendError, invoke_backend


class SequentialBackendPool:
    def __init__(self, factories, lock_timeout_seconds=0.0):
        if (
            not isinstance(factories, dict)
            or not factories
            or any(
                not isinstance(key, str) or not callable(value)
                for key, value in factories.items()
            )
            or type(lock_timeout_seconds) not in (int, float)
            or lock_timeout_seconds < 0
        ):
            raise ValueError("invalid_backend_pool_configuration")
        self.factories = dict(factories)
        self.lock_timeout_seconds = lock_timeout_seconds
        self._lock = threading.Lock()
        self._active_id = None
        self._active_backend = None

    def _close_active(self):
        backend, self._active_backend = self._active_backend, None
        self._active_id = None
        if backend is not None:
            close = getattr(backend, "close", None)
            if callable(close):
                close()

    def run(self, backend_id, source, metadata, checkpoint):
        if backend_id not in self.factories:
            raise BackendError("backend_configuration_unavailable")
        if not self._lock.acquire(timeout=self.lock_timeout_seconds):
            raise BackendError("backend_capacity_timeout")
        try:
            if self._active_id != backend_id:
                self._close_active()
                try:
                    backend = self.factories[backend_id]()
                except MemoryError:
                    raise BackendError("backend_resource_capacity_exceeded") from None
                self._active_id, self._active_backend = backend_id, backend
            try:
                return invoke_backend(
                    self._active_backend, source, metadata, checkpoint
                )
            except MemoryError:
                self._close_active()
                raise BackendError("backend_resource_capacity_exceeded") from None
            except BackendError:
                self._close_active()
                raise
        finally:
            self._lock.release()

    def close(self):
        if not self._lock.acquire(timeout=self.lock_timeout_seconds):
            raise BackendError("backend_capacity_timeout")
        try:
            self._close_active()
        finally:
            self._lock.release()

    def resource_receipt(self):
        return {
            "schema_version": "sequential_asr_backend_pool_v1",
            "configured_backend_ids": sorted(self.factories),
            "maximum_simultaneously_loaded_backends": 1,
            "requests_serialized": True,
            "measured_memory_admission": False,
            "memory_estimate_used": False,
        }
