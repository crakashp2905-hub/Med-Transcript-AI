import pytest

from services.asr.backend import BackendError, inspect_backend, invoke_backend
from services.asr.parakeet_backend import ParakeetOnnxBackend


def test_parakeet_candidate_requires_local_exact_artifacts(tmp_path):
    backend = ParakeetOnnxBackend(
        tmp_path,
        "0bbb45a3365852604aef28b538a8f066f4ccaa85",
        {"config.json": "a" * 64},
        "local-model-license",
    )
    contract = inspect_backend(backend)
    assert contract["availability"]["status"] == "integrity_failed"
    assert contract["availability"]["automatic_download"] is False
    assert contract["timestamp_capability"] == {"kind": "none", "native": False}
    with pytest.raises(BackendError, match="backend_unavailable"):
        invoke_backend(
            backend,
            "missing.wav",
            {"channels": 1, "sample_rate": 16000},
            lambda: None,
        )


def test_parakeet_runtime_receipt_is_cpu_text_only(tmp_path):
    backend = ParakeetOnnxBackend(
        tmp_path,
        "0bbb45a3365852604aef28b538a8f066f4ccaa85",
        {"config.json": "a" * 64},
        "local-model-license",
    )
    receipt = backend.runtime_receipt()
    assert receipt["device"] == "cpu"
    assert receipt["automatic_download"] is False
    assert backend.confidence_capability()["supported"] is False
