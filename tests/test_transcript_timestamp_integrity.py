from types import SimpleNamespace

import pytest

from services.asr.adapter import ASRFailure
from services.asr.transcripts import build_transcript


PROFILE = SimpleNamespace(
    engine="test",
    runtime_version="1",
    sha256="a" * 64,
    profile_id="fixture",
    source="local",
    revision="r",
    artifacts=[],
)
META = {"duration_ms": 2000, "sha256": "b" * 64}


def test_transcript_records_gaps_and_preserves_original_timeline():
    result = build_transcript(
        {
            "duration_seconds": 2,
            "segments": [{"start_seconds": 0, "end_seconds": 0.5, "text": "hello"}],
        },
        META,
        "e",
        "u",
        PROFILE,
        "t",
        1,
    )
    assert result["untranscribed_intervals"]
    assert result["provenance"]["timeline_mapping_status"] == "original_pcm_timeline"
    assert result["segments"][0]["timestamp_kind"] == "unknown"
    assert result["provenance"]["word_alignment_status"] == "not_provided"


def test_audio_segment_trace_reports_union_coverage_gaps_and_uncertainty():
    result = build_transcript(
        {
            "duration_seconds": 2,
            "segments": [
                {"start_seconds": 0, "end_seconds": 0.5, "text": "first"},
                {"start_seconds": 0.4, "end_seconds": 0.75, "text": "overlap"},
                {"start_seconds": 1, "end_seconds": 1.5, "text": "later"},
            ],
        },
        META,
        "e",
        "u",
        PROFILE,
        "t",
        1,
    )

    trace = result["timeline_trace"]
    assert trace["input_sha256"] == META["sha256"]
    assert trace["duration_ms"] == 2000
    assert trace["covered_ms"] == 1250
    assert trace["uncovered_ms"] == 750
    assert trace["coverage_percent"] == 62.5
    assert [(gap["start_ms"], gap["end_ms"]) for gap in trace["gaps"]] == [
        (750, 1000),
        (1500, 2000),
    ]
    assert len(trace["segments"]) == 3
    assert "overlapping_model_timestamps" in trace["uncertainty_flags"]
    assert "untranscribed_intervals_require_review" in trace["uncertainty_flags"]
    assert trace["clinical_completeness"] == "unverified"


def test_native_whisper_segment_times_are_not_claimed_as_word_alignment():
    profile = SimpleNamespace(**{**PROFILE.__dict__, "engine": "faster-whisper"})
    result = build_transcript(
        {
            "duration_seconds": 2,
            "segments": [{"start_seconds": 0, "end_seconds": 0.5, "text": "hello"}],
        },
        META,
        "e",
        "u",
        profile,
        "t",
        1,
    )
    assert result["segments"][0]["timestamp_kind"] == "native_segment"
    assert result["segments"][0]["alignment_status"] == "model_estimated"
    assert result["provenance"]["word_alignment_status"] == "not_provided"


@pytest.mark.parametrize(
    "segments",
    [
        [{"start_seconds": 0.5, "end_seconds": 0.4, "text": "bad"}],
        [
            {"start_seconds": 0, "end_seconds": 1, "text": "one"},
            {"start_seconds": 0, "end_seconds": 1.5, "text": "one"},
        ],
    ],
)
def test_transcript_rejects_invalid_or_nonmonotonic_timestamps(segments):
    with pytest.raises(ASRFailure, match="invalid_asr_output"):
        build_transcript(
            {"duration_seconds": 2, "segments": segments},
            META,
            "e",
            "u",
            PROFILE,
            "t",
            1,
        )


def test_digital_silence_cannot_have_hallucinated_segments():
    with pytest.raises(ASRFailure, match="invalid_asr_output"):
        build_transcript(
            {
                "duration_seconds": 2,
                "digital_silence": True,
                "segments": [
                    {"start_seconds": 0, "end_seconds": 1, "text": "hallucination"}
                ],
            },
            META,
            "e",
            "u",
            PROFILE,
            "t",
            1,
        )
