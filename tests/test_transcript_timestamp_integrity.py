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
