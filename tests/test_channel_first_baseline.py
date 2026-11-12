from services.channel_first_baseline import compare


def test_channel_first_baseline_keeps_pipeline_metrics_and_roles_separate():
    result = compare(
        {"speech_ms": 100, "missed_ms": 2, "false_alarm_ms": 3},
        {"speech_ms": 90, "missed_ms": 4, "false_alarm_ms": 5},
    )
    assert result["channel_first"]["speech_ms"] == 100
    assert result["single_mic"]["false_alarm_ms"] == 5
    assert result["role_accuracy"] is None and result["clinical_acceptance"] is False
