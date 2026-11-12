"""Source-only segmentation plans with explicit source-time coverage."""

STRATEGIES = frozenset(
    {"fixed_window", "overlap_aware", "pause_aware", "vad_cut_merge", "channel_first"}
)


def _validated_spans(spans, total_frames):
    result = []
    for span in spans:
        if (
            not isinstance(span, (tuple, list))
            or len(span) != 2
            or type(span[0]) is not int
            or type(span[1]) is not int
            or not 0 <= span[0] < span[1] <= total_frames
        ):
            raise ValueError("invalid_source_time_span")
        result.append((span[0], span[1]))
    return sorted(result)


def _fixed(total_frames, window_frames, overlap_frames):
    spans, start = [], 0
    while start < total_frames:
        end = min(total_frames, start + window_frames)
        spans.append((start, end))
        if end == total_frames:
            break
        start = end - overlap_frames
    return spans


def _pause_aware(total_frames, rate, window_frames, pauses):
    spans, start = [], 0
    while start < total_frames:
        target = min(total_frames, start + window_frames)
        if target == total_frames:
            end = target
        else:
            search_start = max(start + rate, target - 5 * rate)
            candidates = [
                min(max(pause_end, search_start), target)
                for _, pause_end in pauses
                if search_start <= pause_end <= target and pause_end > start
            ]
            end = (
                min(candidates, key=lambda point: abs(point - target))
                if candidates
                else target
            )
        spans.append((start, end))
        start = end
    return spans


def _vad_cut_merge(total_frames, window_frames, vad_spans, padding_frames):
    padded = [
        (max(0, start - padding_frames), min(total_frames, end + padding_frames))
        for start, end in vad_spans
    ]
    merged = []
    for start, end in padded:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    output = []
    for start, end in merged:
        cursor = start
        while end - cursor > window_frames:
            boundary = cursor + window_frames
            output.append((cursor, boundary))
            cursor = boundary
        if cursor < end:
            output.append((cursor, end))
    return output


def build_coverage_ledger(source_spans, windows):
    """Report omitted/duplicated annotated source spans against model windows."""
    source = sorted(source_spans)
    missing, duplicate = [], []
    for start, end in source:
        boundaries = {start, end}
        for window_start, window_end in windows:
            if window_start < end and window_end > start:
                boundaries.add(max(start, window_start))
                boundaries.add(min(end, window_end))
        points = sorted(boundaries)
        for left, right in zip(points, points[1:]):
            coverage = sum(a <= left and b >= right for a, b in windows)
            if coverage == 0:
                missing.append((left, right))
            elif coverage > 1:
                duplicate.append((left, right, coverage))
    return {
        "source_spans": source,
        "windows": sorted(windows),
        "missing_source_spans": missing,
        "duplicated_source_spans": duplicate,
        "complete": not missing,
    }


def plan_segments(
    total_frames,
    sample_rate,
    strategy,
    *,
    max_window_ms=30000,
    overlap_ms=2000,
    vad_spans=(),
    pause_spans=(),
    speech_spans=(),
    channel_count=1,
    source_channels_known=False,
):
    """Create frozen source-coordinate windows; never inspect transcript text."""
    if (
        type(total_frames) is not int
        or total_frames <= 0
        or type(sample_rate) is not int
        or sample_rate <= 0
        or strategy not in STRATEGIES
        or type(max_window_ms) is not int
        or max_window_ms <= 0
        or type(overlap_ms) is not int
        or overlap_ms < 0
    ):
        raise ValueError("invalid_segmentation_profile")
    if type(channel_count) is not int or channel_count < 1:
        raise ValueError("invalid_channel_count")
    window_frames = max(1, sample_rate * max_window_ms // 1000)
    overlap_frames = sample_rate * overlap_ms // 1000
    if strategy == "overlap_aware" and overlap_frames >= window_frames:
        raise ValueError("overlap_must_be_shorter_than_window")
    speech = _validated_spans(speech_spans, total_frames)
    if strategy in {"vad_cut_merge", "pause_aware"} and not speech:
        raise ValueError("source_speech_spans_required_for_coverage_ledger")
    if strategy == "fixed_window":
        windows = _fixed(total_frames, window_frames, 0)
    elif strategy == "overlap_aware":
        windows = _fixed(total_frames, window_frames, overlap_frames)
    elif strategy == "pause_aware":
        pauses = _validated_spans(pause_spans, total_frames)
        windows = _pause_aware(total_frames, sample_rate, window_frames, pauses)
    elif strategy == "vad_cut_merge":
        vad = _validated_spans(vad_spans, total_frames)
        if not vad:
            raise ValueError("vad_candidate_spans_required")
        windows = _vad_cut_merge(total_frames, window_frames, vad, sample_rate // 10)
    else:
        if channel_count < 2:
            raise ValueError("channel_first_requires_multiple_channels")
        windows = _fixed(total_frames, window_frames, 0)

    channels = range(channel_count) if strategy == "channel_first" else (None,)
    planned = []
    for channel in channels:
        for index, (start, end) in enumerate(windows):
            planned.append(
                {
                    "window_id": f"{strategy}:{channel if channel is not None else 'mix'}:{index}",
                    "start_frame": start,
                    "end_frame_exclusive": end,
                    "channel_index": channel,
                    "source_channel_identity_known": bool(
                        source_channels_known and channel is not None
                    ),
                }
            )
    ledger = build_coverage_ledger(speech or [(0, total_frames)], windows)
    if strategy in {"vad_cut_merge", "pause_aware"} and not ledger["complete"]:
        raise ValueError("segmentation_omitted_source_speech")
    return {
        "schema_version": "source_segmentation_plan_v1",
        "strategy": strategy,
        "sample_rate": sample_rate,
        "total_frames": total_frames,
        "parameters": {
            "max_window_ms": max_window_ms,
            "overlap_ms": overlap_ms if strategy == "overlap_aware" else 0,
            "padding_ms": 100 if strategy == "vad_cut_merge" else 0,
            "source_channels_known": bool(source_channels_known),
        },
        "windows": planned,
        "coverage_ledger": ledger,
        "denominator_policy": "all_source_speech_spans_must_remain_covered",
    }
