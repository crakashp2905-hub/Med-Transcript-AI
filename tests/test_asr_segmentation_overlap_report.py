import hashlib
import json

import pytest

from services.asr.segmentation_overlap_report import build_overlap_stitch_report
from services.detailed_benchmark import fast_score


def _fixture(tmp_path, monkeypatch, *, wrong_audio=False):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    cases = []
    report_cases = []
    for index in range(16):
        group_id = f"case-{index:02}"
        reference = "I patient takes 500 mg daily"
        cases.append(
            {
                "group_id": group_id,
                "condition": "clean",
                "foreground_id": f"foreground-{index:02}",
                "donor_id": None,
                "audio": f"case-{index:02}.wav",
                "audio_sha256": f"{index + 1:064x}",
                "reference_turns": [{"reference": reference}],
            }
        )
        actual = "I patient takes uh 500 mg patient takes 500 mg daily"
        report_cases.append(
            {
                "group_id": group_id,
                "condition": "clean",
                "audio_sha256": (
                    "f" * 64 if wrong_audio and index == 0 else f"{index + 1:064x}"
                ),
                "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
                "failed": False,
                "failure_policy": "any_failed_window_empty_hypothesis_full_reference_deletion",
                "window_count": 2,
                "reference_words": len(reference.split()),
                "normalized_edits": fast_score(reference, actual)["normalized_edits"],
                "hypothesis": actual,
                "reference": reference,
                "chunks": [
                    {"hypothesis": "I patient takes uh 500 mg"},
                    {"hypothesis": "patient takes 500 mg daily"},
                ],
            }
        )
    manifest = {"cases": cases}
    suite = {
        "manifest_sha256": "a" * 64,
        "jobs": [
            {
                "candidate_id": "faster-whisper-tiny.en",
                "source_profile_sha256": "b" * 64,
            }
        ],
    }
    monkeypatch.setattr(
        "services.asr.segmentation_overlap_report.validate_suite",
        lambda _: (suite_path, suite, manifest_path, manifest),
    )
    source = {
        "schema_version": "asr_segmentation_mode_receipt_v1",
        "complete": True,
        "configuration": {
            "mode": "overlap_aware",
            "candidate_id": "faster-whisper-tiny.en",
            "profile_sha256": "b" * 64,
        },
        "bindings": {
            "suite_sha256": hashlib.sha256(b"{}").hexdigest(),
            "manifest_sha256": "a" * 64,
            "source_sha256": {"runner": "c" * 64},
        },
        "cases": report_cases,
    }
    receipt = tmp_path / "overlap.json"
    receipt.write_text(json.dumps(source), encoding="utf-8")
    return suite_path, receipt


def test_overlap_report_compares_alignment_on_identical_saved_windows(
    tmp_path, monkeypatch
):
    suite_path, receipt = _fixture(tmp_path, monkeypatch)

    report = build_overlap_stitch_report(
        receipt, tmp_path / "stitch.json", suite_path=suite_path
    )

    assert report["complete"] is True
    assert report["inference_executed"] is False
    assert report["case_count"] == 16
    assert report["failed_samples"] == 0
    assert report["wer_admission_maximum"] == 0.05
    assert report["arms"]["sequence_alignment_stitch"]["normalized_edits"] == 16
    assert report["arms"]["exact_stitch"]["normalized_edits"] > 0
    assert (
        report["arms"]["sequence_alignment_stitch"][
            "fuzzy_events_requiring_audio_review"
        ]
        == 16
    )
    assert all(row["audio_review_required"] for row in report["cases"])


def test_overlap_report_rejects_changed_input_hash(tmp_path, monkeypatch):
    suite_path, receipt = _fixture(tmp_path, monkeypatch, wrong_audio=True)

    with pytest.raises(ValueError, match="overlap_stitch_case_input_mismatch"):
        build_overlap_stitch_report(
            receipt, tmp_path / "stitch.json", suite_path=suite_path
        )
