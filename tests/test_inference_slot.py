import subprocess
import sys
from services.inference_slot import (
    MIN_FREE_MEMORY_RESERVE_BYTES,
    admission_capacity_bytes,
    estimate_model_request_bytes,
    local_inference_slot,
    memory_request_fits,
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
