import csv
import json
from pathlib import Path

from services.api.ingest import file_sha256
from services.review.clinical import MEDICATION, NEGATION, QUANTITY


def test_saved_critical_token_errors_resolve_to_frozen_reference_turns():
    manifest_path = Path("evaluation/datasets/meddistract-detailed-v1/manifest.json")
    report_path = Path("evaluation/reports/error-taxonomy-v2/report.json")
    csv_path = Path("evaluation/reports/error-taxonomy-v2/all-errors.csv")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    protocol = json.loads(
        Path("evaluation/error-taxonomy-protocol-v2.json").read_text(encoding="utf-8")
    )
    assert report["manifest_sha256"] == file_sha256(manifest_path)
    assert protocol["manifest_sha256"] == file_sha256(manifest_path)
    assert report["csv_sha256"] == file_sha256(csv_path)

    source = {case["group_id"]: case for case in manifest["cases"]}
    declared_reports = {
        item["path"]: item["sha256"] for item in protocol["source_reports"]
    }
    assert {item["path"]: item["sha256"] for item in report["reports"]} == (
        declared_reports
    )
    for path, digest in declared_reports.items():
        assert file_sha256(path) == digest
    seen_reports = set()
    reference_errors = critical_errors = insertion_errors = 0
    with csv_path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            case = source.get(row["case"])
            assert case is not None
            assert row["report"] in declared_reports
            seen_reports.add(row["report"])
            tokens = (row["reference_token"], row["hypothesis_token"])
            critical_errors += int(
                any(
                    value
                    and (
                        MEDICATION.search(value)
                        or QUANTITY.search(value)
                        or NEGATION.search(value)
                        or "allerg" in value.lower()
                    )
                    for value in tokens
                )
            )
            if row["operation"] == "insertion":
                insertion_errors += 1
                assert not row["reference_index"]
                assert row["reference_role"] == "unattributed_insertion"
                assert not row["start_ms"] and not row["end_ms"]
                continue

            reference_errors += 1
            assert row["reference_index"].isdigit()
            assert row["reference_token"]
            assert row["start_ms"].isdigit() and row["end_ms"].isdigit()
            assert int(row["start_ms"]) < int(row["end_ms"])
            role = (
                "doctor"
                if row["reference_role"] == "clinician"
                else row["reference_role"]
            )
            assert any(
                turn["role"] == role
                and turn["start_ms"] == int(row["start_ms"])
                and turn["end_ms"] == int(row["end_ms"])
                for turn in case["reference_turns"]
            )

    assert seen_reports == set(declared_reports)
    assert reference_errors > 0 and insertion_errors > 0 and critical_errors > 0
