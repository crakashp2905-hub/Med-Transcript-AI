from services.diarization_adversarial import evaluate_challenges


def test_turn_swap_counterexample_is_visible_after_global_cluster_mapping():
    result = evaluate_challenges()[0]
    assert result["case_id"] == "turn_swap_last_patient_turn"
    assert result["metrics"]["confused_speaker_ms"] == 1000
    assert result["metrics"]["diarization_error_rate"] == 0.25


def test_interruption_and_overlap_collapse_preserve_overlap_error_budget():
    interruption, overlap = evaluate_challenges()[1:]
    assert interruption["metrics"]["reference_overlap_ms"] == 500
    assert interruption["metrics"]["missed_speaker_ms"] == 500
    assert interruption["metrics"]["overlap_error_speaker_ms"] == 500
    assert overlap["metrics"]["reference_overlap_ms"] == 500
    assert overlap["metrics"]["confused_speaker_ms"] == 500
    assert overlap["metrics"]["overlap_error_speaker_ms"] == 500
