import hashlib
import json
import sys
import types
import wave

import pytest

from services.benchmark_text import run


def test_text_benchmark_cannot_relax_five_percent_policy():
    with pytest.raises(ValueError, match="above 5%"):
        run("unused", "whisper", None, None, None, "unused", maximum=.051)


def test_whisper_text_comparison_reuses_model_and_counts_failures(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("{}")
    profile = types.SimpleNamespace(model_dir=str(model), revision="a" * 40,
        profile_id="test", runtime_version="1.2.1", device="cpu", compute_type="int8",
        cpu_threads=4, beam_size=5, sha256="b" * 64, artifacts={"config.json": hashlib.sha256(b"{}").hexdigest()}, verify_artifacts=lambda: None)
    monkeypatch.setattr("services.asr.profiles.load_profiles", lambda _: {"test": profile})
    monkeypatch.setattr("importlib.metadata.version", lambda _: "1.2.1")
    loads, predictions = [], []

    class Model:
        def __init__(self, *args, **kwargs):
            loads.append(kwargs)

        def transcribe(self, audio, **kwargs):
            predictions.append(kwargs)
            if len(predictions) == 2:
                raise RuntimeError("inference failed")
            return iter([types.SimpleNamespace(text="No drug allergies")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    audio = tmp_path / "clip.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\1\0" * 16000)
    samples = [{"sample_id": str(i), "group_id": "one", "language": "en", "audio": audio.name,
        "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(), "reference": "No drug allergies"} for i in range(2)]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dataset_id": "test", "split_role": "test", "data_class": "synthetic",
        "rights_reviewed": True, "samples": samples}))
    result = run(manifest, "whisper", None, None, None, tmp_path / "out.json", profiles="test", profile_id="test")
    assert len(loads) == 1 and len(predictions) == 2
    assert all(p["beam_size"] == 5 and not p["vad_filter"] and not p["condition_on_previous_text"] for p in predictions)
    assert (result["reference_words"], result["normalized_edits"], result["failed_samples"]) == (6, 3, 1)
    assert result["samples"][1]["hypothesis"] == ""
    assert result["wer_gate"]["maximum_normalized_wer"] == .05
    assert result["wer_gate"]["status"] == "fail"
    assert result["api_integration_gate"] == "text_only_adapter_not_admitted_for_clinical_publication"
