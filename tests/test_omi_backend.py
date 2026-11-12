import pytest

from services.asr.backend import BackendError, inspect_backend, invoke_backend
from services.asr.omi_backend import OmiBackend


def test_omi_candidate_is_text_only_and_never_loads_absent_weights(
    tmp_path, monkeypatch
):
    backend = OmiBackend(
        tmp_path,
        "revision-1",
        "omi-med-stt-v1-q8_0.gguf",
        "a" * 64,
        "local-license",
    )
    monkeypatch.setattr(
        "services.omi_adapter.OmiPredictor",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Unavailable weights must not initialize a runtime")
        ),
        raising=False,
    )
    contract = inspect_backend(backend)
    assert contract["availability"]["automatic_download"] is False
    assert contract["timestamp_capability"] == {"kind": "none", "native": False}
    assert contract["confidence_capability"]["supported"] is False
    with pytest.raises(BackendError, match="backend_unavailable"):
        invoke_backend(
            backend,
            "missing.wav",
            {"channels": 1, "sample_rate": 16000},
            lambda: None,
        )
