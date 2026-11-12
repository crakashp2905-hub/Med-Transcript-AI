"""Truthful labels for whether ASR output came from inference or transport."""

from services.asr.adapter import ASRFailure

REAL_MODEL_INFERENCE = "real_model_inference"
SYNTHETIC_TRANSCRIPT_REPLAY = "synthetic_transcript_replay"
MEASURED_DIGITAL_SILENCE = "measured_digital_silence_no_inference"
NO_INFERENCE_UNVERIFIED = "no_inference_unverified_output"
MEASURED_TRANSCRIPTION_QUALITY = "measured_transcription_quality"
SOFTWARE_TRANSPORT_TEST = "software_transport_test"
FAILED_ASR_EVALUATION = "failed_asr_evaluation_without_observed_inference"


def evaluation_evidence_class(rows):
    """Keep transport/replay outputs out of transcription-quality evidence."""
    modes = [row.get("inference_mode") for row in rows]
    if modes and any(mode == REAL_MODEL_INFERENCE for mode in modes):
        return MEASURED_TRANSCRIPTION_QUALITY
    if any(row.get("status") == "failed" for row in rows):
        return FAILED_ASR_EVALUATION
    return SOFTWARE_TRANSPORT_TEST


def is_quality_evidence(report):
    """Validate explicit or historically attributable quality evidence."""
    evidence_class = report.get("evidence_class")
    if evidence_class is not None:
        return evidence_class == MEASURED_TRANSCRIPTION_QUALITY
    # Historical benchmark reports predate the explicit field. Retain them only
    # when they bind a concrete model runtime and preserve every hypothesis.
    samples = report.get("samples")
    return bool(
        isinstance(report.get("profile_id"), str)
        and report["profile_id"]
        and isinstance(report.get("model_revision"), str)
        and len(report["model_revision"]) in (40, 64)
        and isinstance(report.get("profile_sha256"), str)
        and len(report["profile_sha256"]) == 64
        and isinstance(samples, list)
        and samples
        and report.get("sample_count") == len(samples)
        and all(
            isinstance(row, dict)
            and isinstance(row.get("sample_id"), str)
            and row.get("status") in {"completed", "failed"}
            and type(row.get("reference_words")) is int
            and type(row.get("normalized_edits")) is int
            for row in samples
        )
    )


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
