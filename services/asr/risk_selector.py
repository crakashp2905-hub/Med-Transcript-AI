"""Deterministic, signal-backed ASR risk records for human review."""

from collections.abc import Mapping
import re


_SIGNAL_REASONS = {
    "engine_disagreement": "engine_disagreement",
    "invalid_number": "invalid_number",
    "uncertain_speech": "uncertain_speech",
    "role_ambiguity": "role_ambiguity",
    "audio_clipping": "audio_clipping",
}
_ALLOWED_SIGNALS = frozenset((*_SIGNAL_REASONS, "digital_silence"))
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def assess_span(span):
    """Return a review record from explicit diagnostics, never a calibrated score.

    Each signal carries the digest and method version of its source diagnostic.
    ``digital_silence`` must come from an audio measurement, not empty ASR text.
    """
    if not isinstance(span, Mapping):
        raise ValueError("span_record_required")
    audio_asset_id = span.get("audio_asset_id")
    transcript_version = span.get("transcript_version")
    start_ms, end_ms = span.get("start_ms"), span.get("end_ms")
    if not isinstance(audio_asset_id, str) or not audio_asset_id.strip():
        raise ValueError("source_link_required")
    if not isinstance(transcript_version, str) or not transcript_version.strip():
        raise ValueError("source_link_required")
    if (
        not isinstance(start_ms, int)
        or isinstance(start_ms, bool)
        or not isinstance(end_ms, int)
        or isinstance(end_ms, bool)
        or start_ms < 0
        or end_ms <= start_ms
    ):
        raise ValueError("invalid_span")

    signals = span.get("signals", {})
    if not isinstance(signals, Mapping) or set(signals) - _ALLOWED_SIGNALS:
        raise ValueError("unsupported_risk_signal")
    for evidence in signals.values():
        if (
            not isinstance(evidence, Mapping)
            or type(evidence.get("observed")) is not bool
            or not isinstance(evidence.get("method"), str)
            or not evidence["method"].strip()
            or _SHA256.fullmatch(evidence.get("evidence_sha256", "")) is None
            or set(evidence) != {"observed", "method", "evidence_sha256"}
        ):
            raise ValueError("risk_signal_provenance_required")

    reasons = [
        reason
        for signal, reason in _SIGNAL_REASONS.items()
        if signals.get(signal, {}).get("observed") is True
    ]
    text = span.get("text", "")
    if not isinstance(text, str):
        raise ValueError("invalid_span_text")
    if signals.get("digital_silence", {}).get("observed") is True and text.strip():
        reasons.append("silence_hallucination")

    return {
        "audio_asset_id": audio_asset_id,
        "transcript_version": transcript_version,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "risk_reasons": tuple(reasons),
        "evidence_signals": tuple(
            {
                "signal": signal,
                "observed": evidence["observed"],
                "method": evidence["method"],
                "evidence_sha256": evidence["evidence_sha256"],
            }
            for signal, evidence in signals.items()
        ),
        "review_required": bool(reasons),
        "risk_score": None,
        "adopted": False,
    }
