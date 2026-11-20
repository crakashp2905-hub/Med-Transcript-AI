import hashlib
import json

import pytest

from services.asr.lexicon_cohort_report import build_cohort_report
from services.evaluation import score


def _write_cohort(tmp_path, include_reserved=False):
    rows = [
        (
            "consultation_a",
            "clean",
            "take paracetamol today",
            "take paracetamol today",
            False,
        ),
        ("consultation_b", "clean", "patient feels well", "patient feels well", False),
        (
            "consultation_b",
            "distracted",
            "no medication today",
            "no medication today",
            False,
        ),
        ("consultation_c", "clean", "paracetamol maybe", "paracetamol maybe", True),
    ]
    if include_reserved:
        rows.append(
            (
                "day5_consultation05",
                "clean",
                "no medication today",
                "no medication today",
                False,
            )
        )
    manifest_cases = []
    arms = {"fixed_baseline": [], "terminology_only": []}
    for index, (
        group,
        condition,
        reference,
        baseline_hypothesis,
        uncertain,
    ) in enumerate(rows):
        case_id = f"{group}__{condition}"
        audio_sha = f"{index + 1:x}" * 64
        manifest_cases.append(
            {
                "group_id": case_id,
                "foreground_id": group,
                "donor_id": None,
                "condition": condition,
                "audio_sha256": audio_sha,
                "reference_turns": [
                    {"reference": reference, "uncertain_reference": uncertain}
                ],
            }
        )
        for arm, hypothesis in (
            ("fixed_baseline", baseline_hypothesis),
            (
                "terminology_only",
                "no paracetamol today"
                if group == "consultation_b" and condition == "distracted"
                else baseline_hypothesis,
            ),
        ):
            reference_hash = hashlib.sha256(reference.encode()).hexdigest()
            metrics = score(reference, hypothesis)
            arms[arm].append(
                {
                    "group_id": case_id,
                    "audio_sha256": audio_sha,
                    "reference_sha256": reference_hash,
                    "foreground_id": group,
                    "condition": condition,
                    "hypothesis": hypothesis,
                    "failed": False,
                    "reference_words": metrics["reference_words"],
                    "normalized_edits": metrics["normalized_edits"],
                }
            )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data_class": "approved_public",
                "rights_reviewed": True,
                "split": "development_not_independent_acceptance",
                "cases": manifest_cases,
            }
        ),
        encoding="utf-8",
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(
        json.dumps({"manifest_sha256": manifest_sha}), encoding="utf-8"
    )
    lexicon_path = tmp_path / "lexicon.json"
    lexicon_path.write_text(
        json.dumps({"entries": [{"term": "paracetamol"}]}), encoding="utf-8"
    )
    lexicon_sha = hashlib.sha256(lexicon_path.read_bytes()).hexdigest()
    receipt_path = tmp_path / "receipt.json"
    comparison_arms = {}
    for arm, cases in arms.items():
        comparison_arms[arm] = {
            "sample_count": len(cases),
            "failed_samples": sum(row["failed"] for row in cases),
            "reference_words": sum(row["reference_words"] for row in cases),
            "normalized_edits": sum(row["normalized_edits"] for row in cases),
        }
    receipt_path.write_text(
        json.dumps(
            {
                "complete": True,
                "clinical_acceptance": False,
                "bindings": {
                    "manifest_sha256": manifest_sha,
                    "lexicon_sha256": lexicon_sha,
                },
                "comparison": {"arms": comparison_arms},
                "arm_outputs": {
                    "fixed_baseline": {"cases": arms["fixed_baseline"]},
                    "terminology_only": {
                        "configuration": {
                            "component_parameters": {
                                "lexicon_sha256": lexicon_sha,
                                "hotwords": "paracetamol",
                            }
                        },
                        "cases": arms["terminology_only"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    reservation_path = tmp_path / "reservation.json"
    reservation_path.write_text(
        json.dumps({"reserved_groups": ["day5_consultation05"]}), encoding="utf-8"
    )
    return manifest_path, lock_path, receipt_path, lexicon_path, reservation_path


def test_cohort_report_reconciles_paired_wer_and_exact_term_false_insertions(tmp_path):
    paths = _write_cohort(tmp_path)
    report = build_cohort_report(*paths)
    assert report["term"] == "paracetamol"
    assert report["inference_executed"] is False
    assert report["summary"]["baseline"]["positive_occurrence_recall"] == 1.0
    assert report["summary"]["biased"]["positive_occurrence_recall"] == 1.0
    assert report["summary"]["baseline"]["negative_cases_with_term_in_hypothesis"] == 0
    assert report["summary"]["biased"]["negative_cases_with_term_in_hypothesis"] == 1
    assert report["summary"]["biased"]["negative_control_false_term_occurrences"] == 1
    assert report["summary"]["biased"]["negative_control_case_count"] == 2
    assert report["summary"]["biased"]["uncertain_only_term_case_count"] == 1
    assert (
        report["summary"]["biased"]["uncertain_only_cases_with_term_in_hypothesis"] == 1
    )
    assert len(report["cases"]) == 8


def test_cohort_report_rejects_reserved_acceptance_groups(tmp_path):
    paths = _write_cohort(tmp_path, include_reserved=True)
    with pytest.raises(ValueError, match="reserved_acceptance_group_in_eval_source"):
        build_cohort_report(*paths)
