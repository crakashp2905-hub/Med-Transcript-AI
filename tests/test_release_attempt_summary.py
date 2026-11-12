import pytest

from services.release_attempt_summary import build_summary, markdown


def test_summary_binds_all_ci_lanes_and_marks_missing_acceptance():
    report = build_summary(
        source_commit="a" * 40,
        run_id="123",
        jobs={
            "python_matrix": "success",
            "frontend": "success",
            "postgres": "success",
            "container": "success",
        },
    )
    text = markdown(report)
    assert report["ci_status"] == "pass"
    assert report["offline_acceptance"]["status"] == "not_available"
    assert "Clinical release authorization: **false**" in text


def test_summary_marks_acceptance_stale_when_commit_differs():
    report = build_summary(
        source_commit="b" * 40,
        run_id="124",
        jobs={
            "python_matrix": "success",
            "frontend": "success",
            "postgres": "success",
            "container": "success",
        },
        acceptance={"source_commit": "a" * 40, "checks": {"tests": "pass"}},
    )
    assert report["offline_acceptance"]["status"] == "stale"


def test_summary_rejects_incomplete_job_matrix():
    with pytest.raises(ValueError, match="summary_ci_job_set_invalid"):
        build_summary(
            source_commit="c" * 40,
            run_id="125",
            jobs={"python_matrix": "success"},
        )
