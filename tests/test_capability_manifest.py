from types import SimpleNamespace

import pytest

from services.asr.adapter import ASRFailure
from services.asr.provenance import (
    MEASURED_DIGITAL_SILENCE,
    REAL_MODEL_INFERENCE,
    SYNTHETIC_TRANSCRIPT_REPLAY,
    aggregate_channel_modes,
    execution_mode,
)
from services.asr.transcripts import build_transcript
from services.capability_manifest import build


PROFILE = SimpleNamespace(
    engine="fixture",
    runtime_version="test",
    sha256="a" * 64,
    profile_id="capability-test",
    source="local",
    revision="fixture",
    artifacts=[],
)
METADATA = {"duration_ms": 1000, "sha256": "b" * 64}


def test_capability_manifest_distinguishes_real_inference_replay_and_silence():
    manifest = build()
    assert manifest["schema_version"] == "subsystem_capability_manifest_v1"
    assert manifest["manifest_kind"] == "declared_capabilities_not_runtime_measurements"
    assert manifest["asr"]["real_model_inference"]["inference_executed"] is True
    replay = manifest["asr"]["synthetic_transcript_replay"]
    assert replay["inference_executed"] is False and replay["text_may_be_predeclared"]
    silence = manifest["asr"]["silent_audio_transport"]
    assert silence["inference_executed"] is False
    assert silence["transcript_text_generated"] is False
    assert manifest["drafting"]["default"] == "deterministic"
    assert manifest["verification"]["model_can_clear_approval_gate"] is False
    assert manifest["clinical_release_authorized"] is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            {"provider_mode": "synthetic_fixture", "segments": []},
            SYNTHETIC_TRANSCRIPT_REPLAY,
        ),
        (
            {"digital_silence": True, "segments": [], "inference_executed": False},
            MEASURED_DIGITAL_SILENCE,
        ),
        ({"segments": [], "inference_executed": True}, REAL_MODEL_INFERENCE),
    ],
)
def test_transcript_provenance_records_execution_mode(raw, expected):
    transcript = build_transcript(
        {"duration_seconds": 1, "segments": [], **raw},
        METADATA,
        "encounter",
        "upload",
        PROFILE,
        "transcript",
        1,
    )
    assert transcript["provenance"]["inference_mode"] == expected


def test_contradictory_fixture_or_silence_inference_is_rejected():
    with pytest.raises(ASRFailure, match="invalid_asr_output"):
        execution_mode(
            {"provider_mode": "synthetic_fixture", "inference_executed": True}
        )
    with pytest.raises(ASRFailure, match="invalid_asr_output"):
        execution_mode(
            {"digital_silence": True, "inference_executed": True, "segments": []}
        )


def test_multichannel_execution_mode_reports_mixed_channels():
    assert (
        aggregate_channel_modes([MEASURED_DIGITAL_SILENCE, REAL_MODEL_INFERENCE])
        == REAL_MODEL_INFERENCE
    )
    assert (
        aggregate_channel_modes([SYNTHETIC_TRANSCRIPT_REPLAY, MEASURED_DIGITAL_SILENCE])
        == "mixed_channel_execution_modes"
    )
