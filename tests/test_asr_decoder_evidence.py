from types import SimpleNamespace

import pytest

from services.asr.adapter import ASRFailure
from services.asr.transcripts import build_transcript


PROFILE = SimpleNamespace(
    engine="faster-whisper",
    runtime_version="1.2.1",
    sha256="a" * 64,
    profile_id="decoder-evidence-test",
    source="local-fixture",
    revision="r",
    artifacts=[],
)
META = {"duration_ms": 1000, "sha256": "b" * 64}


def test_transcript_preserves_native_best_sequence_without_claiming_nbest():
    evidence = {
        "kind": "faster_whisper_best_sequence_v1",
        "token_ids": [13, 27, 42],
        "average_logprob": -0.42,
        "n_best_supported": False,
        "calibrated": False,
    }
    result = build_transcript(
        {
            "duration_seconds": 1,
            "segments": [
                {
                    "start_seconds": 0,
                    "end_seconds": 0.5,
                    "text": "hello",
                    "decoder_evidence": evidence,
                }
            ],
        },
        META,
        "encounter",
        "upload",
        PROFILE,
        "transcript",
        1,
    )
    segment = result["segments"][0]
    assert segment["decoder_evidence"] == evidence
    assert segment["timestamp_kind"] == "native_segment"
    assert segment["alignment_status"] == "model_estimated"


@pytest.mark.parametrize(
    "evidence",
    [
        {
            "kind": "faster_whisper_best_sequence_v1",
            "token_ids": [1, True],
            "average_logprob": -0.2,
            "n_best_supported": False,
            "calibrated": False,
        },
        {
            "kind": "faster_whisper_best_sequence_v1",
            "token_ids": [1],
            "average_logprob": 0.2,
            "n_best_supported": False,
            "calibrated": False,
        },
        {
            "kind": "faster_whisper_best_sequence_v1",
            "token_ids": [1],
            "average_logprob": -0.2,
            "n_best_supported": True,
            "calibrated": False,
        },
    ],
)
def test_transcript_rejects_misrepresented_decoder_evidence(evidence):
    with pytest.raises(ASRFailure, match="invalid_asr_output"):
        build_transcript(
            {
                "duration_seconds": 1,
                "segments": [
                    {
                        "start_seconds": 0,
                        "end_seconds": 0.5,
                        "text": "hello",
                        "decoder_evidence": evidence,
                    }
                ],
            },
            META,
            "encounter",
            "upload",
            PROFILE,
            "transcript",
            1,
        )
