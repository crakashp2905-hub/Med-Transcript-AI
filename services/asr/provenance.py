"""Truthful labels for whether ASR output came from inference or transport."""

from services.asr.adapter import ASRFailure

REAL_MODEL_INFERENCE = "real_model_inference"
SYNTHETIC_TRANSCRIPT_REPLAY = "synthetic_transcript_replay"
MEASURED_DIGITAL_SILENCE = "measured_digital_silence_no_inference"
NO_INFERENCE_UNVERIFIED = "no_inference_unverified_output"


def execution_mode(raw):
    """Classify adapter output without treating transcript text as inference."""
    if not isinstance(raw, dict):
        raise ASRFailure("invalid_asr_output")
    executed = raw.get("inference_executed") is True
    if raw.get("provider_mode") == "synthetic_fixture":
        if executed:
            raise ASRFailure("invalid_asr_output")
        return SYNTHETIC_TRANSCRIPT_REPLAY
    if raw.get("digital_silence") is True:
        if executed or raw.get("segments"):
            raise ASRFailure("invalid_asr_output")
        return MEASURED_DIGITAL_SILENCE
    if executed:
        return REAL_MODEL_INFERENCE
    return NO_INFERENCE_UNVERIFIED


def aggregate_channel_modes(modes):
    modes = list(modes)
    if not modes:
        return NO_INFERENCE_UNVERIFIED
    if REAL_MODEL_INFERENCE in modes:
        return REAL_MODEL_INFERENCE
    if all(mode == MEASURED_DIGITAL_SILENCE for mode in modes):
        return MEASURED_DIGITAL_SILENCE
    if all(mode == SYNTHETIC_TRANSCRIPT_REPLAY for mode in modes):
        return SYNTHETIC_TRANSCRIPT_REPLAY
    if all(mode == NO_INFERENCE_UNVERIFIED for mode in modes):
        return NO_INFERENCE_UNVERIFIED
    return "mixed_channel_execution_modes"
