from services.asr.postprocess import suggest
import pytest


def test_postprocessor_keeps_raw_negation_and_dose_separate_from_suggestions():
    raw = [
        {"text": "Patient denies warfarin 0.5 mg", "uncertainties": ["unreviewed_asr"]}
    ]
    result = suggest(
        raw,
        [
            {
                "segment_index": 0,
                "suggested_text": "Patient denies warfarin 5 mg",
                "reason": "review",
            }
        ],
    )
    assert result["raw_segments"][0]["text"] == raw[0]["text"]
    assert result["correction_suggestions"][0]["suggested_text"].endswith("5 mg")
    assert result["postprocessing_status"] == "advisory_only"
    assert result["correction_suggestions"][0]["risk_reasons"] == [
        "numeric_or_unit_substitution_requires_review"
    ]
    assert result["correction_suggestions"][0]["review_required"] is True
    assert result["correction_suggestions"][0]["adopted"] is False


def test_medication_and_dose_substitutions_are_flagged_without_adoption():
    result = suggest(
        [{"text": "Take aspirin 75 mg daily."}],
        [
            {
                "segment_index": 0,
                "suggested_text": "Take amlodipine 5 mg daily.",
                "reason": "synthetic safety test",
            }
        ],
    )
    proposal = result["correction_suggestions"][0]
    assert proposal["original_text"] == "Take aspirin 75 mg daily."
    assert proposal["risk_reasons"] == [
        "medication_substitution_requires_review",
        "numeric_or_unit_substitution_requires_review",
    ]
    assert proposal["adopted"] is False
    assert result["raw_segments"][0]["text"] == "Take aspirin 75 mg daily."
    assert result["automatic_adoption"] is False


def test_invalid_suggestion_index_fails_closed():
    with pytest.raises(ValueError, match="suggestion_segment_index_invalid"):
        suggest(
            [{"text": "Take aspirin."}],
            [{"segment_index": 1, "suggested_text": "Take amlodipine."}],
        )
