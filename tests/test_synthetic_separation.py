import json
from pathlib import Path


def test_synthetic_oracle_reports_are_separate_from_public_benchmark_claims():
    report = json.loads(
        Path(
            "evaluation/reports/completion-clinical-models-v2-2026-10-25.json"
        ).read_text(encoding="utf-8")
    )
    assert report.get("data_class") in ("synthetic", "developer_synthetic")
    assert report.get("clinical_acceptance") is False
    assert (
        report.get("annotation_status") == "developer_authored_not_clinician_calibrated"
    )
    assert report.get("complete") is True
