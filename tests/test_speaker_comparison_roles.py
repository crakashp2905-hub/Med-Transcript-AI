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


def test_role_error_budgets_prioritize_patient_and_report_short_response_coverage():
    reference = [
        {
            "start_ms": 0,
            "end_ms": 400,
            "role": "patient",
            "text": "No.",
        },
        {
            "start_ms": 500,
            "end_ms": 1800,
            "role": "clinician",
            "text": "Please describe the symptoms you noticed yesterday.",
        },
    ]
    predicted = [
        {"start_ms": 0, "end_ms": 200, "speaker_id": "patient-cluster"},
    ]

    result = role_metrics(reference, predicted, {"patient-cluster": "patient"})

    assert result["patient"]["priority_label"] == "high"
    assert result["clinician"]["priority_label"] == "standard"
    assert result["priority_metrics"]["short_response_count"] == 1
    assert result["priority_metrics"]["short_response_missed_count"] == 1
    assert result["priority_metrics"]["short_response_covered_ms"] == 200
    assert result["priority_metrics"]["short_response_time_recall"] == 0.5
    assert (
        result["priority_metrics"]["threshold_status"]
        == "engineering_priority_heuristic_not_clinical_gold"
    )
