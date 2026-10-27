"""Keep model admission locks independent of running development workspaces."""
import pytest


@pytest.fixture(autouse=True)
def isolated_inference_lock(tmp_path, monkeypatch):
    monkeypatch.setenv('MED_TRANSCRIPT_INFERENCE_LOCK', str(tmp_path / 'inference.lock'))
