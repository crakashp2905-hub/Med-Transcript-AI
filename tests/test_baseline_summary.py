from services.baseline_summary import summarize
import pytest


def test_historical_scopes_reproduce_without_combining_datasets_or_qualifying_models():
    report = summarize()
    assert [
        (row["normalized_edits"], row["reference_words"]) for row in report["scopes"]
    ] == [(197, 2264), (679, 5204), (2245, 13683), (2356, 13683)]
    assert report["universal_combined_wer"] is None
    assert all(row["five_percent_gate"] == "fail" for row in report["scopes"])
    assert all(
        row["exact_preservation_cases"]
        + row["incorrect_nonfailed_cases"]
        + row["failed_cases"]
        == row["failure_inclusive_case_count"]
        and row["non_exact_cases"]
        == row["incorrect_nonfailed_cases"] + row["failed_cases"]
        for row in report["draft_preservation"]
    )
    assert [
        (
            row["mode"],
            row["metric"],
            row["failure_inclusive_case_count"],
            row["exact_preservation_cases"],
            row["non_exact_cases"],
            row["incorrect_nonfailed_cases"],
            row["failed_cases"],
            row["clinical_accuracy"],
        )
        for row in report["draft_preservation"]
    ] == [
        (
            "deterministic",
            "synthetic_source_fact_preservation",
            8,
            8,
            0,
            0,
            0,
            "not_measured",
        ),
        (
            "qwen2.5:1.5b",
            "synthetic_source_fact_preservation",
            8,
            3,
            5,
            3,
            2,
            "not_measured",
        ),
        (
            "qwen2.5:7b",
            "synthetic_source_fact_preservation",
            8,
            0,
            8,
            0,
            8,
            "not_measured",
        ),
    ]
    assert not report["clinical_release"] and not report["automatic_model_promotion"]


def test_changed_historical_source_cannot_be_reported_as_the_original_baseline(
    monkeypatch,
):
    monkeypatch.setattr("services.baseline_summary.sha256", lambda path: "0" * 64)
    with pytest.raises(ValueError, match="historical_baseline_source_changed"):
        summarize()
