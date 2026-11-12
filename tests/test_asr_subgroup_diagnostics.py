import json
from pathlib import Path

from services.api.ingest import file_sha256
from services.asr.subgroup_diagnostics import aggregate


def test_subgroups_preserve_unknown_roles_and_include_missing_cases_as_deletions():
    manifest = {
        "dataset_id": "synthetic-subgroups-v1",
        "cases": [
            {
                "group_id": "clean-1",
                "foreground_id": "consultation-1",
                "condition": "clean",
                "reference_turns": [
                    {
                        "start_ms": 0,
                        "end_ms": 800,
                        "role": "doctor",
                        "reference": "No fever",
                    },
                    {
                        "start_ms": 200,
                        "end_ms": 1000,
                        "role": "patient",
                        "reference": "Pain",
                    },
                ],
            },
            {
                "group_id": "distracted-1",
                "foreground_id": "consultation-2",
                "condition": "distracted",
                "reference_turns": [
                    {
                        "start_ms": 0,
                        "end_ms": 700,
                        "role": "unknown",
                        "reference": "Cough",
                    }
                ],
            },
        ],
    }
    reports = [
        {
            "path": "saved-run.json",
            "sha256": "a" * 64,
            "candidate_id": "fixture-asr",
            "mode": "fixed",
            "complete": False,
            "cases": [
                {
                    "id": "clean-1",
                    "failed": False,
                    "reference_words": 3,
                    "normalized_edits": 2,
                }
            ],
        }
    ]
    edits = [
        {
            "report": "saved-run.json",
            "case": "clean-1",
            "candidate": "fixture-asr",
            "mode": "fixed",
            "operation": "substitution",
            "reference_role": "clinician",
            "start_ms": "0",
            "end_ms": "800",
        },
        {
            "report": "saved-run.json",
            "case": "clean-1",
            "candidate": "fixture-asr",
            "mode": "fixed",
            "operation": "insertion",
            "reference_role": "unattributed_insertion",
            "start_ms": "",
            "end_ms": "",
        },
    ]

    run = aggregate(manifest, reports, edits)["runs"][0]
    condition = run["dimensions"]["recording_condition"]
    assert condition["clean"]["reference_words"] == 3
    assert condition["clean"]["substitutions"] == 1
    assert condition["clean"]["unattributed_insertions"] == 1
    assert condition["distracted"]["reference_words"] == 1
    assert condition["distracted"]["deletions"] == 1
    assert condition["distracted"]["missing_outputs"] == 1
    roles = run["dimensions"]["reference_role"]
    assert roles["clinician"]["substitutions"] == 1
    assert roles["patient"]["reference_words"] == 1
    assert roles["unknown"]["deletions"] == 1
    overlap = run["dimensions"]["overlap_status"]
    assert overlap["overlapping"]["reference_words"] == 3
    assert run["dimensions"]["turn_length"]["short_lt_1s"]["reference_words"] == 4
    assert (
        run["dimensions"]["annotated_turn_duration"]["short_lt_30s"][
            "annotated_turn_duration_ms"
        ]
        == 2300
    )
    assert run["channel_mapping"]["status"] == "unknown_not_measured"


def test_saved_real_cohort_subgroups_reconcile_all_reference_denominators():
    path = Path("evaluation/reports/asr-subgroups-v1.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    manifest_path = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
    receipt_path = Path("evaluation/reports/error-taxonomy-v2/report.json")
    errors_path = Path("evaluation/reports/error-taxonomy-v2/all-errors.csv")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert report["manifest_sha256"] == file_sha256(manifest_path)
    assert report["taxonomy_receipt_sha256"] == file_sha256(receipt_path)
    assert report["error_csv_sha256"] == file_sha256(errors_path)
    assert len(report["runs"]) == len(receipt["reports"]) == 17

    source_reports = {row["path"]: row["sha256"] for row in receipt["reports"]}
    expected_words = 27366
    for run in report["runs"]:
        assert source_reports[run["source_report"]] == run["source_report_sha256"]
        condition = run["dimensions"]["recording_condition"]
        assert condition["clean"]["reference_words"] == 13683
        assert condition["distracted"]["reference_words"] == 13683
        for dimension in run["dimensions"].values():
            assert sum(row["reference_words"] for row in dimension.values()) == (
                expected_words
            )
        assert run["channel_mapping"]["status"] == "unknown_not_measured"
