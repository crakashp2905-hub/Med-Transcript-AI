import pytest

from services.asr.retranscribe_span import retranscribe_span


def test_retranscribe_span_is_linked_candidate_only():
    result = retranscribe_span(
        audio_asset_id="audio",
        start_ms=100,
        end_ms=500,
        source_transcript_version="tx-1",
        candidate_text="No allergy.",
    )
    assert result["status"] == "candidate_review_required"
    assert result["adopted"] is False and result["requires_explicit_review"] is True
    assert result["start_ms"] == 100 and result["end_ms"] == 500


def test_retranscribe_span_rejects_invalid_offsets():
    with pytest.raises(ValueError, match="invalid_span"):
        retranscribe_span(
            audio_asset_id="audio",
            start_ms=500,
            end_ms=100,
            source_transcript_version="tx-1",
            candidate_text="text",
        )
