import pytest

from services.diarization_evaluation import score_turns


def test_der_and_jer_are_zero_after_optimal_anonymous_cluster_mapping():
    reference = [
        {"start_ms": 0, "end_ms": 1000, "role": "clinician"},
        {"start_ms": 1000, "end_ms": 2000, "role": "patient"},
    ]
    predicted = [
        {"start_ms": 0, "end_ms": 1000, "speaker_id": "cluster-b"},
        {"start_ms": 1000, "end_ms": 2000, "speaker_id": "cluster-a"},
    ]

    result = score_turns(reference, predicted)

    assert result["diarization_error_rate"] == 0
    assert result["speaker_jaccard_error_rate"] == 0
    assert result["overlap_policy"] == "score_all"
    assert result["scoring_mapping_is_not_clinician_role_confirmation"] is True


def test_collar_excludes_exact_configured_time_around_internal_reference_turns():
    reference = [
        {"start_ms": 0, "end_ms": 1000, "role": "clinician"},
        {"start_ms": 1000, "end_ms": 2000, "role": "patient"},
    ]
    predicted = [
        {"start_ms": 0, "end_ms": 1000, "speaker_id": "a"},
        {"start_ms": 1000, "end_ms": 2000, "speaker_id": "b"},
    ]

    result = score_turns(reference, predicted, collar_ms=100)

    assert result["collar_ms"] == 100
    assert result["ignored_collar_ms"] == 200
    assert result["reference_speaker_ms"] == 1800
    assert result["diarization_error_rate"] == 0


def test_overlap_policy_can_exclude_reference_overlap_without_hiding_accounting():
    reference = [
        {"start_ms": 0, "end_ms": 2000, "role": "clinician"},
        {"start_ms": 1000, "end_ms": 3000, "role": "patient"},
    ]
    predicted = [
        {"start_ms": 0, "end_ms": 2000, "speaker_id": "a"},
        {"start_ms": 1000, "end_ms": 3000, "speaker_id": "b"},
    ]

    result = score_turns(
        reference, predicted, overlap_policy="ignore_reference_overlap"
    )

    assert result["reference_speaker_ms"] == 2000
    assert result["ignored_reference_overlap_ms"] == 1000
    assert result["overlap_policy"] == "ignore_reference_overlap"
    assert result["reference_overlap_ms"] == 0


def test_overlap_scored_reports_reference_overlap_and_overlap_error_budget():
    reference = [
        {"start_ms": 0, "end_ms": 2000, "role": "clinician"},
        {"start_ms": 1000, "end_ms": 3000, "role": "patient"},
    ]

    result = score_turns(reference, [])

    assert result["reference_overlap_ms"] == 1000
    assert result["overlap_error_speaker_ms"] == 2000


def test_explicit_predicted_roles_report_role_misattribution_separately_from_clusters():
    reference = [{"start_ms": 0, "end_ms": 1000, "role": "clinician"}]
    predicted = [
        {
            "start_ms": 0,
            "end_ms": 1000,
            "speaker_id": "cluster-a",
            "role": "patient",
        }
    ]
    result = score_turns(reference, predicted)
    assert result["diarization_error_rate"] == 0
    assert result["role_attribution_scored"] is True
    assert result["role_misattributed_ms"] == 1000
    assert result["role_attribution_error_rate"] == 1


def test_anonymous_clusters_do_not_claim_role_accuracy():
    reference = [{"start_ms": 0, "end_ms": 1000, "role": "clinician"}]
    predicted = [{"start_ms": 0, "end_ms": 1000, "speaker_id": "cluster-a"}]
    result = score_turns(reference, predicted)
    assert result["role_attribution_scored"] is False
    assert result["role_attribution_error_rate"] is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"collar_ms": True}, "invalid_diarization_collar"),
        ({"collar_ms": -1}, "invalid_diarization_collar"),
        ({"overlap_policy": "guess"}, "invalid_diarization_overlap_policy"),
    ],
)
def test_diarization_scoring_rejects_invalid_policies(kwargs, message):
    with pytest.raises(ValueError, match=message):
        score_turns([], [], **kwargs)
