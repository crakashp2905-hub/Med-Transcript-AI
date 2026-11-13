from services.speaker_comparison import role_metrics


def test_role_metrics_count_time_mapped_to_the_other_confirmed_role():
    reference = [
        {"start_ms": 0, "end_ms": 1000, "role": "clinician"},
        {"start_ms": 1000, "end_ms": 2000, "role": "patient"},
    ]
    predicted = [
        {"start_ms": 0, "end_ms": 1000, "speaker_id": "a"},
        {"start_ms": 1000, "end_ms": 2000, "speaker_id": "b"},
    ]

    result = role_metrics(
        reference,
        predicted,
        {"a": "patient", "b": "clinician"},
    )

    assert result["clinician"]["role_swap_ms"] == 1000
    assert result["patient"]["role_swap_ms"] == 1000
