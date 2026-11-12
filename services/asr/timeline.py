"""Build compact audio-to-segment coverage traces for clinician source review."""


def _union_duration(intervals):
    covered = 0
    end = 0
    for start, stop in sorted(intervals):
        start = max(0, start)
        if stop <= start:
            continue
        covered += max(0, stop - max(start, end))
        end = max(end, stop)
    return covered


def build_audio_segment_trace(duration_ms, input_sha256, segments, gaps, review_flags):
    """Summarize timestamp coverage without treating it as clinical completeness."""
    by_channel = {}
    intervals = []
    trace_segments = []
    uncertainty_flags = set(review_flags)
    for segment in segments:
        channel = segment.get("channel_index", 0)
        start, end = segment["start_ms"], segment["end_ms"]
        intervals.append((start, end))
        by_channel.setdefault(channel, []).append((start, end))
        uncertainty_flags.update(segment.get("uncertainties", []))
        trace_segments.append(
            {
                "segment_id": segment["segment_id"],
                "start_ms": start,
                "end_ms": end,
                "channel_index": channel,
                "speaker_id": segment.get("speaker_id"),
                "role": segment.get("role", "unknown"),
                "role_status": segment.get("role_status", "unconfirmed"),
                "uncertainties": list(segment.get("uncertainties", [])),
            }
        )
    for gap in gaps:
        channel = gap.get("channel_index", 0)
        by_channel.setdefault(channel, [])
        uncertainty_flags.add("untranscribed_intervals_require_review")
    covered_ms = min(duration_ms, _union_duration(intervals))
    channels = [
        {
            "channel_index": channel,
            "covered_ms": min(duration_ms, _union_duration(channel_intervals)),
        }
        for channel, channel_intervals in sorted(by_channel.items())
    ]
    return {
        "schema_version": "audio_segment_trace_v1",
        "input_sha256": input_sha256,
        "duration_ms": duration_ms,
        "covered_ms": covered_ms,
        "uncovered_ms": max(0, duration_ms - covered_ms),
        "coverage_percent": round(covered_ms * 100 / duration_ms, 2)
        if duration_ms
        else 0.0,
        "segments": trace_segments,
        "gaps": [dict(gap) for gap in gaps],
        "channels": channels,
        "review_flags": sorted(set(review_flags)),
        "uncertainty_flags": sorted(uncertainty_flags),
        "clinical_completeness": "unverified",
    }
