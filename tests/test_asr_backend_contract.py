import hashlib

import pytest

from services.asr.adapter import FasterWhisperAdapter
from services.asr.backend import BackendError, inspect_backend, invoke_backend
from services.asr.profiles import ASRProfile, REQUIRED_FILES


_DEFAULT = object()


class FakeBackend:
    def __init__(self, *, status="available_not_admitted", result=_DEFAULT, error=None):
        self.status = status
        self.result = (
            {"segments": [{"text": "hello"}]} if result is _DEFAULT else result
        )
        self.error = error
        self.calls = 0

    def availability(self):
        return {"status": self.status}

    def timestamp_capability(self):
        return {"kind": "none", "native": False}

    def n_best_capability(self):
        return {"supported": False, "kind": "none"}

    def confidence_capability(self):
        return {"supported": False, "kind": "none", "calibrated": False}

    def runtime_receipt(self):
        return {
            "backend_id": "fake",
            "runtime_version": "test",
            "model_revision": "fake-revision",
        }

    def transcribe(self, source, metadata, checkpoint):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_fake_backend_capabilities_and_runtime_receipt_are_explicit():
    backend = FakeBackend()
    contract = inspect_backend(backend)
    assert contract["n_best_capability"]["supported"] is False
    assert contract["confidence_capability"]["supported"] is False
    result = invoke_backend(backend, "audio", {}, lambda: None)
    assert result["result"] == {"segments": [{"text": "hello"}]}
    assert result["runtime_receipt"]["backend_id"] == "fake"


def test_unavailable_model_is_rejected_before_backend_call():
    backend = FakeBackend(status="unavailable")
    with pytest.raises(BackendError, match="backend_unavailable"):
        invoke_backend(backend, "audio", {}, lambda: None)
    assert backend.calls == 0


def test_timeout_and_malformed_outputs_fail_closed():
    with pytest.raises(BackendError, match="backend_timeout"):
        invoke_backend(
            FakeBackend(error=TimeoutError()),
            "audio",
            {},
            lambda: None,
        )
    for result in (None, {"segments": "bad"}, {"segments": [{"text": 1}]}):
        with pytest.raises(BackendError, match="backend_output_invalid"):
            invoke_backend(FakeBackend(result=result), "audio", {}, lambda: None)


def test_faster_whisper_adapter_reports_unsupported_confidence_truthfully(tmp_path):
    for name in REQUIRED_FILES:
        (tmp_path / name).write_bytes(b"fixture")
    profile = ASRProfile(
        profile_id="backend-contract",
        model_dir=str(tmp_path),
        source="synthetic",
        revision="a" * 40,
        license_id="test-only",
        artifacts={
            name: hashlib.sha256(b"fixture").hexdigest() for name in REQUIRED_FILES
        },
    )
    backend = FasterWhisperAdapter(profile)
    contract = inspect_backend(backend)
    assert contract["timestamp_capability"] == {
        "kind": "segment",
        "native": True,
        "word_alignment_validated": False,
    }
    assert contract["confidence_capability"]["supported"] is False
    assert contract["runtime_receipt"]["profile_sha256"] == profile.sha256
