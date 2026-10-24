import hashlib
import json
import wave
from collections import Counter
from pathlib import Path

from services.benchmark_ranking import rank
from services.evaluation import PROJECT_MAX_NORMALIZED_WER

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/datasets/primock57-expanded-v1"


def test_expanded_audio_protocol_and_prior_group_separation():
    raw = (CORPUS / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    lock = json.loads((CORPUS / "lock.json").read_text())
    assert hashlib.sha256(raw).hexdigest() == lock["manifest_sha256"]
    protocol = ROOT / "evaluation/expanded-protocol-v1.json"
    assert manifest["protocol_sha256"] == hashlib.sha256(protocol.read_bytes()).hexdigest()
    assert len(manifest["samples"]) == lock["sample_count"] == 118
    groups = {s["group_id"] for s in manifest["samples"]}
    assert len(groups) == 20
    assert Counter(g.split("_")[0] for g in groups) == {f"day{i}": 4 for i in range(1, 6)}
    for folder in ("primock57-smoke-v1", "primock57-validation-v1"):
        old = json.loads((ROOT / f"evaluation/datasets/{folder}/manifest.json").read_text())
        assert groups.isdisjoint({s["group_id"] for s in old["samples"]})
    duration = 0
    for sample in manifest["samples"]:
        audio = CORPUS / sample["audio"]
        assert "<" not in sample["reference"]
        assert hashlib.sha256(audio.read_bytes()).hexdigest() == sample["audio_sha256"]
        with wave.open(str(audio), "rb") as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 16000)
            duration += stream.getnframes() / stream.getframerate()
    assert abs(duration - lock["audio_seconds"]) < .0001
    assert lock["maximum_normalized_wer"] == PROJECT_MAX_NORMALIZED_WER == .05


def test_all_locally_measured_configurations_are_predeclared_without_hosted_jobs():
    suite = json.loads((ROOT / "evaluation/expanded-suite-v1.json").read_text())
    previous = json.loads((ROOT / "evaluation/leaderboard.json").read_text())
    assert {j["candidate_id"] for j in suite["jobs"]} == {r["candidate_id"] for r in previous["ranked"]}
    assert len(suite["jobs"]) == 7
    assert {j["runtime"] for j in suite["jobs"]} == {"whisper", "onnx", "omi"}
    # Historical 3% and current 5% locks remain separately reproducible.
    assert rank(CORPUS / "manifest.json", CORPUS / "lock.json", [], ROOT)["maximum_normalized_wer"] == .05
