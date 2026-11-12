from services.baseline_summary import summarize
import pytest


def test_historical_scopes_reproduce_without_combining_datasets_or_qualifying_models():
    report = summarize()
    assert [
        (row["normalized_edits"], row["reference_words"]) for row in report["scopes"]
    ] == [(197, 2264), (679, 5204), (2245, 13683), (2356, 13683)]
    assert report["universal_combined_wer"] is None
    assert all(row["five_percent_gate"] == "fail" for row in report["scopes"])
    assert report["draft_preservation"] == [
        {
            "mode": "deterministic",
            "attempted_cases": 8,
            "exact_preservation_cases": 8,
            "failed_cases": 0,
        },
        {
            "mode": "qwen2.5:1.5b",
            "attempted_cases": 8,
            "exact_preservation_cases": 3,
            "failed_cases": 2,
        },
        {
            "mode": "qwen2.5:7b",
            "attempted_cases": 8,
            "exact_preservation_cases": 0,
            "failed_cases": 8,
        },
    ]
    assert not report["clinical_release"] and not report["automatic_model_promotion"]


def test_changed_historical_source_cannot_be_reported_as_the_original_baseline(
    monkeypatch,
):
    monkeypatch.setattr("services.baseline_summary.sha256", lambda path: "0" * 64)
    with pytest.raises(ValueError, match="historical_baseline_source_changed"):
        summarize()
