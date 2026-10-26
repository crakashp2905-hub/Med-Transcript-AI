"""Validate raw adapter output and preserve honest original-timeline provenance."""

import math
from uuid import uuid4

from services.asr.adapter import ASRFailure


def build_transcript(raw, metadata, encounter_id, upload_id, profile, transcript_id, version):
    if not isinstance(raw, dict):
        raise ASRFailure("invalid_asr_output")
    duration = metadata["duration_ms"]
    reported = raw.get("duration_seconds")
    if (isinstance(reported, bool) or not isinstance(reported, (int, float))
            or not math.isfinite(reported) or abs(reported * 1000 - duration) > 1):
        raise ASRFailure("invalid_asr_output")
    rows = raw.get("segments")
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ASRFailure("invalid_asr_output")
    segments, gaps, last_start, covered, total_chars = [], [], -1, 0, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ASRFailure("invalid_asr_output")
        start, end, text = row.get("start_seconds"), row.get("end_seconds"), row.get("text")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (start, end)):
            raise ASRFailure("invalid_asr_output")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ASRFailure("invalid_asr_output")
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise ASRFailure("invalid_asr_output") from None
        total_chars += len(text)
        if total_chars > 500_000 or start < 0 or end <= start or end * 1000 > duration + 1:
            raise ASRFailure("invalid_asr_output")
        start_ms, end_ms = round(start * 1000), round(end * 1000)
        if start_ms < last_start or end_ms <= start_ms or end_ms > duration:
            raise ASRFailure("invalid_asr_output")
        if start_ms > covered:
            gaps.append({"start_ms": covered, "end_ms": start_ms, "reason": "not_transcribed_unknown_cause"})
        uncertainties = ["unreviewed_asr", "language_support_unverified", "speaker_unassigned"]
        if start_ms < covered:
            uncertainties.append("overlapping_model_timestamps")
        segments.append({"segment_id": str(uuid4()), "start_ms": start_ms, "end_ms": end_ms,
                         "text": text, "speaker_id": None, "role": "unknown", "role_status": "unconfirmed",
                         "language": "en", "language_status": "uncertain", "alignment_status": "model_estimated",
                         "uncertainties": uncertainties,
                         "raw_start_seconds": start, "raw_end_seconds": end})
        covered, last_start = max(covered, end_ms), start_ms
    if covered < duration:
        gaps.append({"start_ms": covered, "end_ms": duration, "reason": "not_transcribed_unknown_cause"})
    flags = ["clinician_review_required", "language_support_unverified", "clinical_coverage_unverified"]
    if not segments:
        flags.append("no_transcribed_speech")
    if raw.get("digital_silence") is True:
        if segments:
            raise ASRFailure("invalid_asr_output")
        flags.append("digital_silence")
    if gaps:
        flags.append("untranscribed_intervals_require_review")
    return {"schema_version": "1.0", "id": transcript_id, "version": version,
            "encounter_id": encounter_id, "audio_asset_id": upload_id,
            "input_sha256": metadata["sha256"], "duration_ms": duration,
            "source_availability": "available", "status": "review_required", "language": "en",
            "segments": segments, "untranscribed_intervals": gaps, "review_flags": flags,
            "provenance": {"engine": profile.engine, "runtime_version": profile.runtime_version,
                "runtime_packages": raw.get("runtime_packages", {}), "timing": raw.get("timing", {}),
                "working_audio_sha256": metadata.get("working_sha256") or metadata["sha256"],
                "timeline_mapping_status": metadata.get("timeline_mapping_status", "original_pcm_timeline"),
                "profile_id": profile.profile_id, "profile_sha256": profile.sha256,
                "model_source": profile.source, "model_revision": profile.revision,
                "preprocessing": "original_mono_16khz_pcm16_to_float32_v1",
                "feature_extractor": "hashed_preprocessor_config" if "preprocessor_config.json" in profile.artifacts
                    else "faster_whisper_1.2.1_defaults",
                "vad_filter": False, "word_timestamps": False,
                "inference_executed": raw.get("inference_executed") is True,
                "adapter_iteration": "finished", "clinical_coverage": "unverified"}}
