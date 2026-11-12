from services.artifact_summary import summarize


def test_artifact_summary_places_failures_first_and_keeps_release_blocked():
    result = summarize(
        {
            "checks": {
                "backend_tests": {"status": "pass"},
                "container": {"status": "blocked_missing_local_artifact"},
            }
        }
    )
    assert result["failure_count"] == 1 and result["failures_first"]
    assert result["markdown"].index("Failures and blocks") < result["markdown"].index(
        "Checks"
    )
    assert result["clinical_release"] == "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED"
