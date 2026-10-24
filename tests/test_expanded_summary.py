import hashlib
import json
from pathlib import Path

import pytest

from services.expanded_summary import summarize
from services.asr.profiles import content_sha256


@pytest.fixture
def results(tmp_path):
    root = tmp_path
    evaluation = root / "evaluation"
    evaluation.mkdir()
    manifest = {"dataset_id": "test", "samples": [
        {"sample_id": "a", "group_id": "day1_one", "speaker_role": "doctor", "reference": "No drug allergies"},
        {"sample_id": "b", "group_id": "day2_two", "speaker_role": "patient", "reference": "No chest pain"}]}
    source = evaluation / "manifest.json"
    source.write_text(json.dumps(manifest))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (evaluation / "lock.json").write_text(json.dumps({"dataset_id": "test", "manifest_sha256": digest,
        "maximum_normalized_wer": .05, "failure_policy": "empty_hypothesis_full_reference_deletions", "allowed_use": "test"}))
    jobs, entries, profiles = [], [], []
    for index in range(7):
        cid = f"model{index}"
        source_profile = {"profile_id": cid, "artifacts": {}, "revision": "c" * 40}
        profiles.append(source_profile)
        source_hash = content_sha256(source_profile)
        jobs.append({"candidate_id": cid, "runtime": "whisper", "profile_id": cid, "source_profile_sha256": source_hash})
        path = f"evaluation/{cid}.json"
        entries.append({"candidate_id": cid, "status": "completed", "report": path})
        report = {"dataset_id": "test", "manifest_sha256": digest,
            "scoring_profile": "lowercase_words_preserve_decimals_units_negation_v1",
            "failure_policy": "empty_hypothesis_full_reference_deletions", "reference_words": 6,
            "normalized_edits": 0, "normalized_wer": 0, "failed_samples": 0, "sample_count": 2,
            "profile_id": cid, "profile_sha256": "a" * 64, "model_revision": "c" * 40,
            "runtime_configuration": {"source_profile_sha256": source_hash, "runtime_version": "1.2.1", "artifacts": {}},
            "samples": [{"sample_id": s["sample_id"], "group_id": s["group_id"], "reference_words": 3,
                "normalized_edits": 0, "status": "completed", "elapsed_seconds": 1,
                "hypothesis": s["reference"]} for s in manifest["samples"]]}
        report["profile_sha256"] = content_sha256(report["runtime_configuration"])
        (root / path).write_text(json.dumps(report))
    (evaluation / "expanded-suite-v1.json").write_text(json.dumps({"manifest": "evaluation/manifest.json", "lock": "evaluation/lock.json", "jobs": jobs}))
    (evaluation / "expanded-ledger.json").write_text(json.dumps({"candidates": entries}))
    (evaluation / "expanded-whisper-profiles.json").write_text(json.dumps(profiles))
    return root


def test_grouped_metrics_do_not_promote_even_passing_models(results):
    result = summarize(results)
    assert len(result["models"]) == 7 and result["maximum_normalized_wer"] == .05
    assert result["production_model_selected"] is None
    for row in result["models"]:
        assert row["wer_gate"]["status"] == "pass"
        assert sum(g["reference_words"] for g in row["by_role"].values()) == 6
        assert sum(g["reference_words"] for g in row["by_consultation"].values()) == 6
        assert sum(g["reference_words"] for g in row["by_day"].values()) == 6


@pytest.mark.parametrize("change", ["profile", "runtime", "missing", "configuration_hash"])
def test_incomplete_or_changed_configurations_cannot_be_published(results, change):
    if change == "missing":
        path = results / "evaluation/expanded-ledger.json"
        body = json.loads(path.read_text())
        body["candidates"].pop()
    else:
        path = results / "evaluation/model0.json"
        body = json.loads(path.read_text())
        if change == "configuration_hash":
            body["profile_sha256"] = "0" * 64
        else:
            key = "source_profile_sha256" if change == "profile" else "runtime_version"
            body["runtime_configuration"][key] = "changed"
            body["profile_sha256"] = content_sha256(body["runtime_configuration"])
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="predeclared|Predeclared"):
        summarize(results)
