from services.source_coverage import analyze


def test_source_coverage_does_not_equate_audio_coverage_with_completeness():
    result = analyze(
        [{"start_ms": 0, "end_ms": 100, "kind": "filler"}],
        duration_ms=200,
        clinical_fact_ids=["f1"],
        covered_fact_ids=[],
    )
    assert result["irrelevant_filler_spans"] == 1
    assert result["clinical_omission_candidates"] == ["f1"]
    assert result["clinical_completeness_claim"] is False
