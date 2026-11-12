"""Candidate-only retranscription of an existing audio span."""


def retranscribe_span(
    *, audio_asset_id, start_ms, end_ms, source_transcript_version, candidate_text
):
    if not audio_asset_id or not source_transcript_version:
        raise ValueError("source_link_required")
    if (
        not isinstance(start_ms, int)
        or not isinstance(end_ms, int)
        or start_ms < 0
        or end_ms <= start_ms
    ):
        raise ValueError("invalid_span")
    if not isinstance(candidate_text, str) or not candidate_text.strip():
        raise ValueError("candidate_text_required")
    return {
        "status": "candidate_review_required",
        "audio_asset_id": audio_asset_id,
        "source_transcript_version": source_transcript_version,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "candidate_text": candidate_text,
        "adopted": False,
        "requires_explicit_review": True,
    }
