from services.publication_bundle import build


def test_publication_tables_retain_gate_failures_unranked_candidates_and_limits():
    bundle = build(".")
    report = bundle["report"]
    assert bundle["inference_performed"] is False
    assert bundle["negative_results_preserved"] is True
    assert report["maximum_normalized_wer"] == 0.05
    assert len(report["models"]) == 7
    assert all(row["wer_gate"]["status"] == "fail" for row in report["models"])
    assert len(report["unranked"]) == 7
    assert all(row["sha256"] for row in bundle["source_reports"])
    assert "Failed clips" in bundle["generated_markdown"]
    assert "Clinical adjudication remains pending" in bundle["generated_markdown"]
    assert bundle["production_model_selected"] is None
