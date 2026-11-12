"""Bounded, fail-closed context handoff for long-form ASR candidates."""

import hashlib
import json
import re


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_context_handoff(previous_candidate, current_window, max_words=24):
    """Pass prior text only with explicit audio review and current speech evidence."""
    if type(max_words) is not int or not 1 <= max_words <= 64:
        raise ValueError("invalid_context_word_limit")
    if not isinstance(previous_candidate, dict) or not isinstance(current_window, dict):
        raise ValueError("context_evidence_records_required")
    previous_text = previous_candidate.get("text")
    previous_span = previous_candidate.get("source_span")
    supported = (
        previous_candidate.get("audio_review_status") == "acoustically_supported"
        and isinstance(previous_candidate.get("source_audio_sha256"), str)
        and len(previous_candidate["source_audio_sha256"]) == 64
        and isinstance(previous_span, dict)
        and type(previous_span.get("start_ms")) is int
        and type(previous_span.get("end_ms")) is int
        and 0 <= previous_span["start_ms"] < previous_span["end_ms"]
        and isinstance(previous_text, str)
        and bool(previous_text.strip())
    )
    current_supported = (
        current_window.get("candidate_activity") == "candidate_speech_present"
        and isinstance(current_window.get("audio_sha256"), str)
        and len(current_window["audio_sha256"]) == 64
    )
    if not supported or not current_supported:
        reason = (
            "prior_candidate_lacks_acoustic_review"
            if not supported
            else "current_window_has_no_speech_candidate"
        )
        return {
            "schema_version": "asr_context_handoff_v1",
            "context_text": "",
            "context_sha256": _digest(""),
            "word_count": 0,
            "status": "context_suppressed",
            "reason": reason,
            "confidence": None,
        }

    words = re.findall(r"\S+", previous_text.strip())[-max_words:]
    context = " ".join(words)
    return {
        "schema_version": "asr_context_handoff_v1",
        "context_text": context,
        "context_sha256": _digest(context),
        "word_count": len(words),
        "status": "bounded_reviewed_context_candidate",
        "reason": None,
        "source_audio_sha256": previous_candidate["source_audio_sha256"],
        "source_span": dict(previous_span),
        "current_audio_sha256": current_window["audio_sha256"],
        "confidence": None,
        "clinical_truth_asserted": False,
    }
