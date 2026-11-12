from services.detailed_campaign import bootstrap


def test_paired_bootstrap_samples_consultation_rows_not_tokens():
    rows = [
        {"group_id": "consultation-a", "normalized_edits": 1, "reference_words": 10},
        {"group_id": "consultation-b", "normalized_edits": 4, "reference_words": 20},
    ]
    result = bootstrap(rows, iterations=100)
    assert result["method"] == "foreground_cluster_percentile_bootstrap"
    assert result["iterations"] == 100 and result["seed"] == 20261029
    assert result["low"] <= result["high"]
