"""Keep model admission locks independent of running development workspaces."""
import pytest


@pytest.fixture(autouse=True)
def isolated_inference_lock(tmp_path, monkeypatch):
    monkeypatch.setenv('MED_TRANSCRIPT_INFERENCE_LOCK', str(tmp_path / 'inference.lock'))
    # Model-free tests use deterministic capacity; actual OS telemetry is checked
    # independently by runtime preflight and must not decide fixture outcomes.
    monkeypatch.setattr('services.inference_slot.available_memory_bytes', lambda: 16 * 1024**3)
