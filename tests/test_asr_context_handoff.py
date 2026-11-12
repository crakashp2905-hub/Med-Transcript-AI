import pytest

from services.asr.context_handoff import build_context_handoff


def _previous(status="acoustically_supported"):
    return {
        "text": "Patient takes metformin 500 mg every day",
        "source_audio_sha256": "a" * 64,
        "source_span": {"start_ms": 1000, "end_ms": 3000},
        "audio_review_status": status,
    }


def test_context_is_bounded_and_bound_to_reviewed_audio():
    result = build_context_handoff(
        _previous(),
        {"audio_sha256": "b" * 64, "candidate_activity": "candidate_speech_present"},
        max_words=4,
    )
    assert result["context_text"] == "500 mg every day"
    assert result["word_count"] == 4
    assert result["clinical_truth_asserted"] is False


@pytest.mark.parametrize(
    ("activity", "reason"),
    [
        ("candidate_silence", "current_window_has_no_speech_candidate"),
        ("indeterminate", "current_window_has_no_speech_candidate"),
    ],
)
def test_context_is_suppressed_for_silent_or_indeterminate_audio(activity, reason):
    result = build_context_handoff(
        _previous(),
        {"audio_sha256": "b" * 64, "candidate_activity": activity},
    )
    assert result["status"] == "context_suppressed"
    assert result["context_text"] == ""
    assert result["reason"] == reason


def test_unreviewed_prior_transcript_cannot_be_carried_forward():
    result = build_context_handoff(
        _previous("unreviewed"),
        {"audio_sha256": "b" * 64, "candidate_activity": "candidate_speech_present"},
    )
    assert result["context_text"] == ""
    assert result["reason"] == "prior_candidate_lacks_acoustic_review"


def test_context_rejects_out_of_range_source_spans():
    previous = _previous()
    previous["source_span"] = {"start_ms": 3000, "end_ms": 1000}
    result = build_context_handoff(
        previous,
        {"audio_sha256": "b" * 64, "candidate_activity": "candidate_speech_present"},
    )
    assert result["status"] == "context_suppressed"
