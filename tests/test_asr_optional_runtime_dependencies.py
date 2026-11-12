import hashlib
import wave
from types import SimpleNamespace

from importlib.metadata import PackageNotFoundError
import pytest

from services.asr.adapter import FasterWhisperAdapter
from services.asr.profiles import ASRProfile, REQUIRED_FILES


def test_wav_transcription_does_not_require_unused_media_runtimes(
    tmp_path, monkeypatch
):
    pytest.importorskip("numpy", reason="numpy is an ASR runtime dependency")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    artifacts = {}
    for name in REQUIRED_FILES:
        content = b"local model fixture"
        (model_dir / name).write_bytes(content)
        artifacts[name] = hashlib.sha256(content).hexdigest()
    profile = ASRProfile(
        profile_id="optional-runtime-dependencies",
        model_dir=str(model_dir),
        source="test-only",
        revision="a" * 40,
        license_id="test-only",
        artifacts=artifacts,
    )

    def package_version(name):
        if name in {"av", "onnxruntime"}:
            raise PackageNotFoundError(name)
        return "1.2.1" if name == "faster-whisper" else "test"

    monkeypatch.setattr(
        "services.asr.adapter.importlib.metadata.version", package_version
    )

    class Model:
        def transcribe(self, samples, **options):
            segment = SimpleNamespace(
                start=0.0,
                end=0.1,
                text="hello",
                tokens=[11, 12],
                avg_logprob=-0.25,
            )
            return iter([segment]), SimpleNamespace(duration=0.1)

    def load(_profile_json):
        return Model()

    load.cache_info = lambda: SimpleNamespace(hits=0)
    monkeypatch.setattr("services.asr.adapter.loaded_model", load)
    audio = tmp_path / "input.wav"
    with wave.open(str(audio), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16000)
        target.writeframes(b"\x01\x00" * 1600)

    result = FasterWhisperAdapter(profile).transcribe(
        audio,
        {"channels": 1, "sample_rate": 16000, "frames": 1600},
        lambda: None,
    )

    assert result["segments"] == [
        {
            "start_seconds": 0.0,
            "end_seconds": 0.1,
            "text": "hello",
            "decoder_evidence": {
                "kind": "faster_whisper_best_sequence_v1",
                "token_ids": [11, 12],
                "average_logprob": -0.25,
                "n_best_supported": False,
                "calibrated": False,
            },
        }
    ]
    assert set(result["runtime_packages"]) == {
        "faster-whisper",
        "ctranslate2",
        "tokenizers",
        "numpy",
    }
