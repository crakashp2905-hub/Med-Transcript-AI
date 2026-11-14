import pytest

from services.evaluation_envelope import build_envelope, run_cases


def _provenance(**changes):
    values = {
        "dataset_id": "fixture-v1",
        "dataset_sha256": "a" * 64,
        "split": "development",
        "model_id": "none",
        "configuration_sha256": "b" * 64,
        "source_code_sha256": "c" * 64,
        "runtime": {"python": "3.x"},
        "hardware": {"platform": "test"},
        "evidence_class": "synthetic_rule_test",
        "wall_seconds": 0.0,
        "limitations": ["synthetic only"],
    }
    return values | changes


def test_envelope_accounts_once_for_success_and_failed_cases():
    envelope = run_cases(
        provenance=_provenance(),
        manifest_case_ids=["ok", "bad", "timeout"],
        evaluate_case=lambda case: (
            {"metric": 1}
            if case == "ok"
            else (_ for _ in ()).throw(
                TimeoutError() if case == "timeout" else RuntimeError()
            )
        ),
    )
    assert envelope["case_count"] == 3
    assert envelope["failure_inclusive_denominator"] == 3
    assert envelope["case_status_counts"] == {
        "succeeded": 1,
        "failed": 1,
        "timed_out": 1,
        "aborted": 0,
        "not_run": 0,
    }
    assert [row["case_id"] for row in envelope["cases"]] == ["ok", "bad", "timeout"]


@pytest.mark.parametrize(
    "rows",
    [[], [{"case_id": "a", "status": "failed"}, {"case_id": "a", "status": "failed"}]],
)
def test_envelope_rejects_missing_or_duplicate_case_accounting(rows):
    with pytest.raises(ValueError):
        build_envelope(
            provenance=_provenance(), manifest_case_ids=["a"], result_rows=rows
        )


def test_envelope_rejects_unknown_evidence_class():
    with pytest.raises(ValueError, match="evidence_class_invalid"):
        build_envelope(
            provenance=_provenance(evidence_class="paid_inference"),
            manifest_case_ids=["a"],
            result_rows=[{"case_id": "a", "status": "failed"}],
        )
