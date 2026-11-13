import subprocess
import sys
from services.inference_slot import (
    MIN_FREE_MEMORY_RESERVE_BYTES,
    admission_capacity_bytes,
    estimate_model_request_bytes,
    local_inference_slot,
    memory_request_fits,
    _register_source_request,
    _source_request_pending,
)


def test_memory_budget_reserves_two_gib_and_applies_configured_cap(monkeypatch):
    monkeypatch.setenv("MED_TRANSCRIPT_LOCAL_MEMORY_BYTES", str(6 * 1024**3))
    monkeypatch.setattr(
        "services.inference_slot.available_memory_bytes", lambda: 8 * 1024**3
    )
    assert admission_capacity_bytes() == 4 * 1024**3
    assert MIN_FREE_MEMORY_RESERVE_BYTES == 2 * 1024**3
    assert memory_request_fits(4 * 1024**3)
    assert not memory_request_fits(4 * 1024**3 + 1)


def test_model_memory_estimate_uses_artifact_bytes_and_fixed_overhead(tmp_path):
    first = tmp_path / "weights.bin"
    second = tmp_path / "config.json"
    first.write_bytes(b"1234")
    second.write_bytes(b"12")
    assert estimate_model_request_bytes([first, second]) == 12 + 512 * 1024**2


def test_process_slot_denies_requests_outside_the_configured_budget(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MED_TRANSCRIPT_LOCAL_MEMORY_BYTES", "1")
    monkeypatch.setenv("MED_TRANSCRIPT_INFERENCE_LOCK", str(tmp_path / "budget.lock"))
    monkeypatch.setattr(
        "services.inference_slot.available_memory_bytes", lambda: 16 * 1024**3
    )
    with local_inference_slot(requested_bytes=1) as ready:
        assert ready is False


def test_second_process_cannot_admit_inference_until_slot_is_released(
    tmp_path, monkeypatch
):
    path = str(tmp_path / "admission.lock")
    monkeypatch.setenv("MED_TRANSCRIPT_INFERENCE_LOCK", path)
    command = [
        sys.executable,
        "-c",
        "from services.inference_slot import local_inference_slot; c=local_inference_slot(requested_bytes=1); print(c.__enter__()); c.__exit__(None,None,None)",
    ]
    with local_inference_slot() as ready:
        assert ready
        blocked = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=15
        )
        assert blocked.stdout.strip() == "False"
    allowed = subprocess.run(
        command, capture_output=True, text=True, check=True, timeout=15
    )
    assert allowed.stdout.strip() == "True"


def test_pending_source_request_defers_optional_inference(tmp_path, monkeypatch):
    lock_path = tmp_path / "priority.lock"
    monkeypatch.setenv("MED_TRANSCRIPT_INFERENCE_LOCK", str(lock_path))
    monkeypatch.setattr(
        "services.inference_slot.available_memory_bytes", lambda: 16 * 1024**3
    )
    marker = _register_source_request(lock_path)
    assert _source_request_pending(lock_path)
    with local_inference_slot(requested_bytes=1, priority="optional") as ready:
        assert ready is False
    marker.unlink()
    assert not _source_request_pending(lock_path)
    with local_inference_slot(requested_bytes=1, priority="optional") as ready:
        assert ready is True


def test_source_request_marker_is_cleared_after_admission(tmp_path, monkeypatch):
    lock_path = tmp_path / "source.lock"
    monkeypatch.setenv("MED_TRANSCRIPT_INFERENCE_LOCK", str(lock_path))
    monkeypatch.setattr(
        "services.inference_slot.available_memory_bytes", lambda: 16 * 1024**3
    )
    with local_inference_slot(requested_bytes=1, priority="source") as ready:
        assert ready is True
        assert _source_request_pending(lock_path)
    assert not _source_request_pending(lock_path)


def test_asr_source_admission_defers_optional_ollama_across_processes(
    tmp_path, monkeypatch
):
    """ASR worker and Ollama routes share one cross-process admission lock."""
    lock_path = tmp_path / "asr-ollama-contention.lock"
    monkeypatch.setenv("MED_TRANSCRIPT_INFERENCE_LOCK", str(lock_path))
    monkeypatch.setattr(
        "services.inference_slot.available_memory_bytes", lambda: 16 * 1024**3
    )
    command = [
        sys.executable,
        "-c",
        "from services.inference_slot import local_inference_slot; "
        "ctx=local_inference_slot(requested_bytes=1, priority='optional'); "
        "print(ctx.__enter__()); ctx.__exit__(None,None,None)",
    ]

    with local_inference_slot(requested_bytes=1, priority="source") as ready:
        assert ready
        deferred = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=15
        )
        assert deferred.stdout.strip() == "False"

    admitted = subprocess.run(
        command, capture_output=True, text=True, check=True, timeout=15
    )
    assert admitted.stdout.strip() == "True"
