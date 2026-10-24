import hashlib
import json
import wave
from pathlib import Path

import pytest

from services.validation_summary import summarize

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/datasets/primock57-validation-v1"


def rebuild(ledger=None, initial=None):
    return summarize(CORPUS / "manifest.json", CORPUS / "lock.json",
        ledger or ROOT / "evaluation/validation-ledger.json",
        initial or ROOT / "evaluation/leaderboard.json", ROOT)


def test_frozen_validation_audio_protocol_and_consultation_separation():
    raw = (CORPUS / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    lock = json.loads((CORPUS / "lock.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == lock["manifest_sha256"]
    assert manifest["protocol_sha256"] == hashlib.sha256((ROOT / "evaluation/validation-protocol-v1.json").read_bytes()).hexdigest()
    old = json.loads((ROOT / "evaluation/datasets/primock57-smoke-v1/manifest.json").read_text())
    groups = {s["group_id"] for s in manifest["samples"]}
    assert groups.isdisjoint({s["group_id"] for s in old["samples"]})
    assert len(groups) == 5 and len(manifest["samples"]) == 30
    for sample in manifest["samples"]:
        audio = CORPUS / sample["audio"]
        assert hashlib.sha256(audio.read_bytes()).hexdigest() == sample["audio_sha256"]
        with wave.open(str(audio), "rb") as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 16000)


def test_summary_reproduces_and_keeps_strict_gate():
    result = rebuild()
    published = json.loads((ROOT / "evaluation/reports/follow-up-validation-2026-10-24.json").read_text())
    assert result == published
    assert result["reference_words"] == 575
    assert all(row["wer_gate"]["status"] == "fail" for row in result["models"])
    for row in result["models"]:
        assert sum(g["normalized_edits"] for g in row["by_consultation"].values()) == row["normalized_edits"]
        assert sum(g["reference_words"] for g in row["by_role"].values()) == 575


def test_missing_finalist_cannot_be_published(tmp_path):
    ledger = json.loads((ROOT / "evaluation/validation-ledger.json").read_text())
    ledger["candidates"].pop()
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match="exactly the predeclared"):
        rebuild(ledger=path)


def test_changed_model_configuration_cannot_be_compared(tmp_path):
    initial = json.loads((ROOT / "evaluation/leaderboard.json").read_text())
    for row in initial["ranked"]:
        row["profile_sha256"] = "0" * 64
    path = tmp_path / "initial.json"
    path.write_text(json.dumps(initial))
    with pytest.raises(ValueError, match="configuration changed"):
        rebuild(initial=path)
