import json
from pathlib import Path


def test_negative_results_index_retains_failures_and_not_run_states():
    report = json.loads(
        Path("evaluation/reports/beccsv-negative-results-index-v1.json").read_text(
            encoding="utf-8"
        )
    )
    result = report["preserved_results"][0]
    assert result["false_alarms"] == 2 and len(result["failures"]) == 2
    assert all(
        item["status"] in {"not_run", "not_available"}
        for item in report["not_run_or_blocked"]
    )
    assert report["success_claim"] is False
    assert report["clinical_gold"] is False
    assert report["dataset_changes"][0]["policy"].startswith("Do not edit in place")
    assert any(
        "contamination" in item["experiment"] for item in report["not_run_or_blocked"]
    )


def test_paper_is_labeled_as_method_hypothesis_with_explicit_limitations():
    paper = Path("docs/research/BECCSV-paper-draft-v0.1.md").read_text(encoding="utf-8")
    normalized = " ".join(paper.casefold().split())
    assert "systems/method-hypothesis draft" in normalized
    assert "frozen-baseline comparison" in normalized
    assert "or independent clinical evaluation has been run" in normalized
    assert "no model promotion or real-patient release" in normalized
    assert "```mermaid" in normalized
    assert "planned baselines" in normalized
    assert "limitations" in normalized
