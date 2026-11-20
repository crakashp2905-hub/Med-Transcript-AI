import hashlib
import json

import pytest

from services.asr.correction_confusion_report import build_confusion_report


def _write_fixture(tmp_path, reserved=False):
    groups = ["day5_consultation05" if reserved else "consultation_a", "consultation_b"]
    cases = []
    manifest_cases = []
    for index, group in enumerate(groups):
        audio_sha = str(index + 1) * 64
        case_id = f"{group}__clean"
        cases.append(
            {
                "id": case_id,
                "foreground_id": group,
                "condition": "clean",
                "input_sha256": audio_sha,
                "failed": False,
                "reference": "take 5 mg daily",
                "hypothesis": "take 5 daily extra",
                "reference_words": 4,
                "normalized_edits": 2,
            }
        )
        manifest_cases.append(
            {
                "group_id": case_id,
                "foreground_id": group,
                "condition": "clean",
                "audio_sha256": audio_sha,
            }
        )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "rights_reviewed": True,
                "data_class": "approved_public",
                "split": "development_not_independent_acceptance",
                "license": "CC-BY-4.0",
                "attribution": "fixture",
                "cases": manifest_cases,
            }
        ),
        encoding="utf-8",
    )
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "complete": True,
                "clinical_acceptance": False,
                "manifest_sha256": hashlib.sha256(
                    manifest_path.read_bytes()
                ).hexdigest(),
                "suite_sha256": "f" * 64,
                "cases": cases,
            }
        ),
        encoding="utf-8",
    )
    return manifest_path, receipt_path


def test_confusion_report_reconciles_edits_and_keeps_groups_out_of_fold(tmp_path):
    manifest_path, receipt_path = _write_fixture(tmp_path)
    report = build_confusion_report(manifest_path, receipt_path)
    assert report["summary"] == {
        "case_count": 2,
        "consultation_group_count": 2,
        "reference_words": 8,
        "normalized_edits": 4,
        "substitutions": 4,
        "deletions": 0,
        "insertions": 0,
        "confusion_rows": 4,
        "failed_cases": 0,
        "wer": 0.5,
    }
    for row in report["training_table"]:
        assert row["held_out_group"] not in row["training_groups_for_fold"]
        assert row["consultation_group"] == row["held_out_group"]
    assert report["model_fit"] is False
    assert report["split_protocol"]["reserved_acceptance_groups_used"] == []


def test_confusion_report_rejects_reserved_acceptance_group(tmp_path):
    manifest_path, receipt_path = _write_fixture(tmp_path, reserved=True)
    with pytest.raises(ValueError, match="reserved_acceptance_group_forbidden"):
        build_confusion_report(manifest_path, receipt_path)
