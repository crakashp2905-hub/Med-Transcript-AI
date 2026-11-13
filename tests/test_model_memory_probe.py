import json
import wave

import pytest

from services import model_memory_probe as probe


def _wav(path, rate=16000, channels=1, width=2):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(width)
        output.setframerate(rate)
        output.writeframes(b"\0" * rate * channels * width)


def test_probe_accepts_only_local_mono_16khz_pcm16(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    source = tmp_path / "source.wav"
    _wav(source)
    result = probe._audio_metadata(source)
    assert result["duration_seconds"] == 1
    assert len(result["sha256"]) == 64

    wrong_rate = tmp_path / "wrong.wav"
    _wav(wrong_rate, rate=8000)
    with pytest.raises(ValueError, match="mono_16khz_pcm16"):
        probe._audio_metadata(wrong_rate)


def test_probe_requires_one_declared_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"jobs": [{"candidate_id": "one"}]}))
    with pytest.raises(ValueError, match="candidate_not_unique"):
        probe._job(suite, "missing")
