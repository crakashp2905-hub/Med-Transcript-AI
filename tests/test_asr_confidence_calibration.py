import pytest

pytest.importorskip("numpy", reason="confidence calibration requires the ASR extra")

from services.asr.confidence_calibration import _cluster_bootstrap, _crossfit


def test_confidence_calibration_crossfits_whole_groups_and_bootstraps_groups():
    groups = ["consultation-1", "consultation-2", "consultation-3", "consultation-4"]
    rows = []
    for index, group in enumerate(groups):
        rows.extend(
            [
                {
                    "consultation_group_id": group,
                    "status": "completed",
                    "decoder_score": -0.1 - index,
                    "exact_match": index % 2 == 0,
                },
                {
                    "consultation_group_id": group,
                    "status": "completed",
                    "decoder_score": -0.2 - index,
                    "exact_match": index % 2 == 1,
                },
            ]
        )

    crossfit = _crossfit(rows, groups)
    for row in crossfit:
        held_out = row["consultation_group_id"]
        assert row["crossfit_held_out_group"] == held_out
        assert held_out not in row["crossfit_training_groups"]
        assert set(row["crossfit_training_groups"]) == set(groups) - {held_out}
        assert 0 <= row["crossfit_probability_exact_match"] <= 1

    interval = _cluster_bootstrap(crossfit, groups)
    assert interval["method"] == "consultation_group_cluster_percentile_bootstrap"
    assert interval["group_count"] == len(groups)
    assert interval["selection_coverage_95_percentile_interval"] is not None
    assert (
        interval["brier_95_percentile_interval"][0]
        <= interval["brier_95_percentile_interval"][1]
    )

    from services.asr.confidence_calibration import _calibration_metrics

    metrics = _calibration_metrics(crossfit, groups)
    assert metrics["out_of_fold_prevalence_baseline_brier_score"] is not None
    assert metrics["brier_skill_vs_prevalence_baseline"] is not None
