import hashlib
import json
import wave
from array import array

import pytest

from services.asr.segmentation_candidate_runner import (
    MODE_CONFIGS,
    combine_receipts,
    evaluate_case,
    validate_suite,
)
from services.api.ingest import file_sha256


def _audio(path, samples):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(array("h", samples).tobytes())
    return path


def _case(path):
    return {
        "group_id": "same-consultation-clean",
        "condition": "clean",
        "foreground_id": "same-consultation",
        "donor_id": None,
        "audio_sha256": file_sha256(path),
        "reference_turns": [{"reference": "hello there"}],
    }


class FakePredictor:
    def __init__(self):
        self.calls = 0

    def __call__(self, path, context):
        self.calls += 1
        with wave.open(str(path), "rb") as audio:
            duration = audio.getnframes() / audio.getframerate()
        return {
            "text": "hello there",
            "segments": [
                {"start_ms": 0.0, "end_ms": duration * 1000, "text": "hello there"}
            ],
        }


@pytest.mark.parametrize("mode", list(MODE_CONFIGS))
def test_segmentation_modes_preserve_input_hashes_and_score_same_reference(
    tmp_path, mode
):
    source = _audio(tmp_path / "source.wav", [10000] * 32000)
    predictor = FakePredictor()

    row = evaluate_case(_case(source), source, predictor, mode)

    assert row["audio_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert row["failed"] is False
    assert row["reference_words"] == 2
    assert row["normalized_edits"] == 0
    assert row["coverage_ledger"]["complete"] is True
    assert row["timestamp_kind"] == "window_approximation_only"
    assert predictor.calls == row["window_count"]


def _receipt(path, mode, suite_sha, manifest_sha, profile_sha, case_rows):
    report = {
        "complete": True,
        "configuration": {
            "mode": mode,
            "mode_parameters": MODE_CONFIGS[mode],
            "profile_sha256": profile_sha,
        },
        "bindings": {
            "suite_sha256": suite_sha,
            "manifest_sha256": manifest_sha,
            "source_sha256": {"runner": "f" * 64},
        },
        "summary": {
            "sample_count": len(case_rows),
            "failed_samples": 0,
            "reference_words": 2 * len(case_rows),
            "normalized_edits": 0,
            "normalized_wer": 0.0,
        },
        "resource_measurement": {"status": "measured", "peak_resident_bytes": 1},
        "cases": case_rows,
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_matrix_requires_same_case_audio_and_reference_hashes(tmp_path, monkeypatch):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_sha = "c" * 64
    profile_sha = "a" * 64
    common = [
        {
            "group_id": "case-1",
            "condition": "clean",
            "foreground_id": "group-1",
            "donor_id": None,
            "audio_sha256": "d" * 64,
            "reference_sha256": hashlib.sha256(b"hello there").hexdigest(),
            "failed": False,
            "hypothesis": "hello there",
            "reference_words": 2,
            "normalized_edits": 0,
        }
    ]
    suite = {
        "manifest_sha256": manifest_sha,
        "jobs": [{"source_profile_sha256": profile_sha}],
    }
    suite_sha = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    manifest = {
        "cases": [
            {
                "group_id": "case-1",
                "condition": "clean",
                "foreground_id": "group-1",
                "donor_id": None,
                "audio_sha256": "d" * 64,
                "reference_turns": [{"reference": "hello there"}],
            }
        ]
    }
    monkeypatch.setattr(
        "services.asr.segmentation_candidate_runner.validate_suite",
        lambda path: (suite_path, suite, manifest_path, manifest),
    )
    receipts = []
    for mode in MODE_CONFIGS:
        path = tmp_path / f"{mode}.json"
        _receipt(path, mode, suite_sha, manifest_sha, profile_sha, common)
        receipts.append(path)

    result = combine_receipts(receipts, tmp_path / "matrix.json", suite_path=suite_path)

    assert result["complete"] is False
    assert result["applicable_modes_complete"] is True
    assert result["case_count"] == 1
    assert result["channel_first"]["status"] == "not_applicable"
    assert set(result["modes"]) == set(MODE_CONFIGS)


def test_matrix_rejects_changed_audio_hash_between_modes(tmp_path, monkeypatch):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_sha = "c" * 64
    profile_sha = "a" * 64
    suite = {
        "manifest_sha256": manifest_sha,
        "jobs": [{"source_profile_sha256": profile_sha}],
    }
    suite_sha = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    manifest = {
        "cases": [
            {
                "group_id": "case-1",
                "condition": "clean",
                "foreground_id": "group-1",
                "donor_id": None,
                "audio_sha256": "d" * 64,
                "reference_turns": [{"reference": "hello there"}],
            }
        ]
    }
    monkeypatch.setattr(
        "services.asr.segmentation_candidate_runner.validate_suite",
        lambda path: (suite_path, suite, manifest_path, manifest),
    )
    receipts = []
    for index, mode in enumerate(MODE_CONFIGS):
        path = tmp_path / f"{mode}.json"
        row = {
            "group_id": "case-1",
            "condition": "clean",
            "foreground_id": "group-1",
            "donor_id": None,
            "audio_sha256": ("d" if index == 0 else "f") * 64,
            "reference_sha256": hashlib.sha256(b"hello there").hexdigest(),
            "failed": False,
            "hypothesis": "hello there",
            "reference_words": 2,
            "normalized_edits": 0,
        }
        _receipt(path, mode, suite_sha, manifest_sha, profile_sha, [row])
        receipts.append(path)

    with pytest.raises(ValueError, match="segmentation_mode_input_mismatch"):
        combine_receipts(receipts, tmp_path / "matrix.json", suite_path=suite_path)


def test_segmentation_child_suite_preserves_frozen_cohort_and_gate():
    parent_path = "evaluation/detailed-suite-v7.json"
    child_path = "evaluation/detailed-suite-v7-segmentation-planner.json"
    parent = json.loads(open(parent_path, encoding="utf-8").read())
    parent_manifest = json.loads(open(parent["manifest"], encoding="utf-8").read())
    _, child, _, child_manifest = validate_suite(child_path)

    assert child["supersedes_suite"] == parent_path
    assert child["supersedes_suite_sha256"] == file_sha256(parent_path)
    assert child["manifest_sha256"] == parent["manifest_sha256"]
    assert child["maximum_normalized_wer"] == parent["maximum_normalized_wer"] == 0.05
    assert child["jobs"] == parent["jobs"]
    assert [case["audio_sha256"] for case in child_manifest["cases"]] == [
        case["audio_sha256"] for case in parent_manifest["cases"]
    ]
