from services.diarization_evaluation import separate_workload_metrics


def test_diarization_metrics_keep_errors_and_role_workload_separate():
    result = separate_workload_metrics(
        {
            "diarization_error_rate": 0.5,
            "missed_speaker_ms": 10,
            "false_alarm_speaker_ms": 20,
            "confused_speaker_ms": 30,
        },
        overlap_error_ms=4,
        role_confirmation_turns=3,
    )
    assert result["diarization_error_rate"] == 0.5 and result["overlap_error_ms"] == 4
    assert (
        result["role_confirmation_turns"] == 3
        and result["clinical_role_accuracy"] is None
    )
