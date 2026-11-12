from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from services.asr.backend import BackendError
from services.asr.resource_router import SequentialBackendPool


class FakeBackend:
    def __init__(self, state, *, entered=None, release=None):
        self.state = state
        self.entered = entered
        self.release = release
        state["loaded"] += 1
        state["maximum_loaded"] = max(state["maximum_loaded"], state["loaded"])

    def availability(self):
        return {"status": "available_not_admitted"}

    def timestamp_capability(self):
        return {"kind": "none", "native": False}

    def n_best_capability(self):
        return {"supported": False}

    def confidence_capability(self):
        return {"supported": False}

    def runtime_receipt(self):
        return {
            "backend_id": "fake",
            "runtime_version": "test",
            "model_revision": "revision",
        }

    def transcribe(self, source, metadata, checkpoint):
        if self.entered:
            self.entered.set()
            assert self.release.wait(3)
        return {"text": "ok", "segments": None}

    def close(self):
        self.state["loaded"] -= 1
        self.state["closed"] += 1


def _state():
    return {"loaded": 0, "maximum_loaded": 0, "closed": 0}


def test_switching_backends_closes_previous_before_loading_next():
    state = _state()
    pool = SequentialBackendPool(
        {backend_id: lambda: FakeBackend(state) for backend_id in ("one", "two")}
    )
    pool.run("one", "a.wav", {}, lambda: None)
    pool.run("two", "b.wav", {}, lambda: None)
    assert state["maximum_loaded"] == 1
    assert state["closed"] == 1
    assert pool.resource_receipt()["measured_memory_admission"] is False
    pool.close()
    assert state["loaded"] == 0


def test_concurrent_request_fails_closed_on_capacity_timeout():
    state = _state()
    entered, release = threading.Event(), threading.Event()
    pool = SequentialBackendPool(
        {"one": lambda: FakeBackend(state, entered=entered, release=release)},
        lock_timeout_seconds=0.05,
    )
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pool.run, "one", "a.wav", {}, lambda: None)
        assert entered.wait(3)
        with pytest.raises(BackendError, match="backend_capacity_timeout"):
            pool.run("one", "b.wav", {}, lambda: None)
        release.set()
        future.result(timeout=3)
    pool.close()


def test_memory_exhaustion_is_translated_and_does_not_leave_active_model():
    pool = SequentialBackendPool({"one": lambda: (_ for _ in ()).throw(MemoryError())})
    with pytest.raises(BackendError, match="backend_resource_capacity_exceeded"):
        pool.run("one", "a.wav", {}, lambda: None)
    assert pool.resource_receipt()["maximum_simultaneously_loaded_backends"] == 1
