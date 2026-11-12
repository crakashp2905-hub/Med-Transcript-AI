import hashlib
import json

import pytest

from services.detailed_benchmark import fast_score
from services.paired_asr_bootstrap import paired_bootstrap, run


def test_bootstrap_resamples_paired_foregrounds_and_keeps_failed_pairs():
    rows = [
        {
            "id": "a-clean",
            "foreground_id": "consult-a",
            "condition": "clean",
            "failed": False,
            "reference_words": 10,
            "normalized_edits": 1,
        },
        {
            "id": "a-noisy",
            "foreground_id": "consult-a",
            "condition": "distracted",
            "failed": False,
            "reference_words": 10,
            "normalized_edits": 3,
        },
        {
            "id": "b-clean",
            "foreground_id": "consult-b",
            "condition": "clean",
            "failed": False,
            "reference_words": 20,
            "normalized_edits": 5,
        },
        {
            "id": "b-noisy",
            "foreground_id": "consult-b",
            "condition": "distracted",
            "failed": True,
            "reference_words": 20,
            "normalized_edits": 20,
        },
    ]
    result = paired_bootstrap(rows, iterations=1000, seed=77)
    repeated = paired_bootstrap(rows, iterations=1000, seed=77)
    assert result == repeated
    assert result["method"] == "resample_foreground_ids_with_both_conditions_intact"
    assert result["estimate"] == pytest.approx(23 / 30 - 6 / 30)
    assert result["paired_foregrounds"] == 2
    assert result["failed_pairs_included"] == 1
    assert result["failed_pairs_excluded"] == 0
    assert [pair["foreground_id"] for pair in result["source_pairs"]] == [
        "consult-a",
        "consult-b",
    ]
    assert result["source_pairs"][1]["distracted"]["failed"] is True
    assert result["low"] <= result["estimate"] <= result["high"]


def test_bootstrap_rejects_dropped_arms_and_incomplete_failure_denominators():
    incomplete = [
        {
            "id": "a-clean",
            "foreground_id": "consult-a",
            "condition": "clean",
            "failed": False,
            "reference_words": 10,
            "normalized_edits": 1,
        }
    ]
    with pytest.raises(ValueError, match="complete_clean_distracted_pairs"):
        paired_bootstrap(incomplete, iterations=1000)
    incomplete[0]["condition"] = "distracted"
    incomplete[0]["failed"] = True
    incomplete[0]["normalized_edits"] = 1
    with pytest.raises(ValueError, match="full_reference_deletions"):
        paired_bootstrap(
            incomplete
            + [
                {
                    **incomplete[0],
                    "id": "a-clean",
                    "condition": "clean",
                    "failed": False,
                    "normalized_edits": 1,
                }
            ],
            iterations=1000,
        )


def test_frozen_report_builder_binds_manifest_runs_and_failed_pairs(tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    manifest_path = dataset / "manifest.json"
    cases = []
    for foreground, clean_text, distracted_text in (
        ("consult-a", "No fever", "Fever"),
        ("consult-b", "Take 5 mg", ""),
    ):
        for condition, hypothesis, failed in (
            ("clean", clean_text, False),
            ("distracted", distracted_text, not bool(distracted_text)),
        ):
            case_id = f"{foreground}-{condition}"
            reference = "No fever" if foreground == "consult-a" else "Take 5 mg"
            cases.append(
                {
                    "group_id": case_id,
                    "foreground_id": foreground,
                    "condition": condition,
                    "audio_sha256": hashlib.sha256(case_id.encode()).hexdigest(),
                    "reference_turns": [{"reference": reference}],
                }
            )
    manifest_path.write_text(
        json.dumps({"dataset_id": "paired-fixture-v1", "cases": cases}),
        encoding="utf-8",
    )
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (dataset / "lock.json").write_text(
        json.dumps({"manifest_sha256": manifest_sha}), encoding="utf-8"
    )
    report_path = tmp_path / "candidate.fixed.json"
    report_rows = []
    for case in cases:
        reference = " ".join(turn["reference"] for turn in case["reference_turns"])
        if case["foreground_id"] == "consult-a":
            hypothesis = "No fever" if case["condition"] == "clean" else "Fever"
            failed = False
        else:
            hypothesis = "Take 5 mg" if case["condition"] == "clean" else ""
            failed = case["condition"] == "distracted"
        report_rows.append(
            {
                "id": case["group_id"],
                "foreground_id": case["foreground_id"],
                "condition": case["condition"],
                "input_sha256": case["audio_sha256"],
                "reference": reference,
                "input_coverage_complete": True,
                "failed": failed,
                "hypothesis": hypothesis,
                **fast_score(reference, hypothesis),
            }
        )
    report_path.write_text(
        json.dumps(
            {
                "candidate_id": "fixture-model",
                "complete": True,
                "manifest_sha256": manifest_sha,
                "mode": "fixed",
                "runtime": {"revision": "a" * 40},
                "cases": report_rows,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "paired.json"
    result = run(manifest_path, [report_path], output_path, iterations=1000, seed=9)
    candidate = result["candidates"][0]
    assert (
        candidate["source_report_sha256"]
        == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )
    assert candidate["paired_bootstrap"]["failed_pairs_included"] == 1
    assert [
        pair["foreground_id"] for pair in candidate["paired_bootstrap"]["source_pairs"]
    ] == [
        "consult-a",
        "consult-b",
    ]
