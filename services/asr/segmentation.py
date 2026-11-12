"""Source-only segmentation plans with explicit source-time coverage."""

from services.conversation_experiment import join_text

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


def _vad_cut_merge(
    total_frames, window_frames, vad_spans, padding_frames, minimum_frames
):
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
    expanded = []
    for start, end in merged:
        if end - start < minimum_frames:
            midpoint = (start + end) // 2
            start = max(0, midpoint - minimum_frames // 2)
            end = min(total_frames, start + minimum_frames)
            start = max(0, end - minimum_frames)
        if expanded and start <= expanded[-1][1]:
            expanded[-1] = (expanded[-1][0], max(expanded[-1][1], end))
        else:
            expanded.append((start, end))
    output = []
    for start, end in expanded:
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


def stitch_window_outputs(plan, outputs):
    """Join outputs by stable window identity and source offsets."""
    expected = {row["window_id"]: row for row in plan.get("windows", [])}
    if not expected or len(outputs) != len(expected):
        raise ValueError("complete_window_output_set_required")
    received = {}
    for output in outputs:
        window_id = output.get("window_id")
        if window_id not in expected or window_id in received:
            raise ValueError("unknown_or_duplicate_window_output")
        text = output.get("text")
        if not isinstance(text, str):
            raise ValueError("window_text_output_required")
        received[window_id] = text
    if set(received) != set(expected):
        raise ValueError("missing_window_output")

    ordered = sorted(
        expected.values(), key=lambda row: (row["start_frame"], row["window_id"])
    )
    transcript, previous_end, events = "", None, []
    for row in ordered:
        text = received[row["window_id"]]
        overlaps = previous_end is not None and row["start_frame"] < previous_end
        if overlaps:
            transcript, removed = join_text(transcript, text, True)
        else:
            transcript, removed = (transcript + " " + text).strip(), 0
        events.append(
            {
                "window_id": row["window_id"],
                "start_frame": row["start_frame"],
                "end_frame_exclusive": row["end_frame_exclusive"],
                "overlapping_source_window": overlaps,
                "removed_tokens": removed,
                "requires_audio_review": removed > 0,
            }
        )
        previous_end = max(previous_end or 0, row["end_frame_exclusive"])
    return {
        "text": transcript,
        "stitch_events": events,
        "review_required": any(event["requires_audio_review"] for event in events),
        "timestamp_kind": "window_approximation_only",
    }


def diagnose_boundaries(turns, windows, short_turn_frames=1600):
    """Measure annotation/window intersections without coercing unknown roles."""
    if type(short_turn_frames) is not int or short_turn_frames < 0:
        raise ValueError("invalid_short_turn_threshold")
    normalized_turns = []
    for turn in turns:
        start, end = turn.get("start_frame"), turn.get("end_frame")
        if (
            not isinstance(turn.get("turn_id"), str)
            or not turn["turn_id"]
            or type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
        ):
            raise ValueError("invalid_annotated_turn")
        normalized_turns.append(turn)
    if len({turn["turn_id"] for turn in normalized_turns}) != len(normalized_turns):
        raise ValueError("duplicate_annotated_turn_id")
    normalized_windows = []
    for window in windows:
        start, end = window.get("start_frame"), window.get("end_frame_exclusive")
        if (
            not isinstance(window.get("window_id"), str)
            or type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
        ):
            raise ValueError("invalid_source_window")
        normalized_windows.append(window)

    turn_rows = []
    for turn in normalized_turns:
        start, end = turn["start_frame"], turn["end_frame"]
        intersections = [
            window
            for window in normalized_windows
            if window["start_frame"] < end and window["end_frame_exclusive"] > start
        ]
        covered = []
        for window in sorted(intersections, key=lambda row: row["start_frame"]):
            left = max(start, window["start_frame"])
            right = min(end, window["end_frame_exclusive"])
            if right > left:
                covered.append((left, right))
        cursor = start
        for left, right in covered:
            if left > cursor:
                break
            cursor = max(cursor, right)
        fully_covered = cursor >= end
        clipped = any(
            start < window["start_frame"] < end
            or start < window["end_frame_exclusive"] < end
            for window in intersections
        )
        duration = end - start
        turn_rows.append(
            {
                "turn_id": turn["turn_id"],
                "role": turn.get("role"),
                "duration_frames": duration,
                "window_ids": [window["window_id"] for window in intersections],
                "status": (
                    "omitted_short_turn"
                    if not intersections and duration <= short_turn_frames
                    else "omitted"
                    if not intersections
                    else "clipped_at_window_boundary"
                    if clipped
                    else "covered"
                    if fully_covered
                    else "partially_uncovered"
                ),
            }
        )
    window_rows = []
    for window in normalized_windows:
        roles = {
            turn.get("role")
            for turn in normalized_turns
            if turn.get("role") is not None
            and turn["start_frame"] < window["end_frame_exclusive"]
            and turn["end_frame"] > window["start_frame"]
        }
        unknown_turns = sum(
            turn.get("role") is None
            and turn["start_frame"] < window["end_frame_exclusive"]
            and turn["end_frame"] > window["start_frame"]
            for turn in normalized_turns
        )
        window_rows.append(
            {
                "window_id": window["window_id"],
                "known_roles": sorted(roles),
                "joined_known_roles": len(roles) > 1,
                "unknown_role_turn_count": unknown_turns,
            }
        )
    return {
        "schema_version": "segmentation_boundary_diagnostics_v1",
        "turns": turn_rows,
        "windows": window_rows,
        "summary": {
            "annotated_turns": len(turn_rows),
            "omitted_short_turns": sum(
                row["status"] == "omitted_short_turn" for row in turn_rows
            ),
            "clipped_turns": sum(
                row["status"] == "clipped_at_window_boundary" for row in turn_rows
            ),
            "partially_uncovered_turns": sum(
                row["status"] == "partially_uncovered" for row in turn_rows
            ),
            "windows_joining_known_roles": sum(
                row["joined_known_roles"] for row in window_rows
            ),
            "windows_with_unknown_role_turns": sum(
                row["unknown_role_turn_count"] > 0 for row in window_rows
            ),
        },
    }


def plan_segments(
    total_frames,
    sample_rate,
    strategy,
    *,
    max_window_ms=30000,
    min_window_ms=1000,
    overlap_ms=2000,
    padding_ms=100,
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
        or type(min_window_ms) is not int
        or min_window_ms <= 0
        or strategy == "vad_cut_merge"
        and min_window_ms > max_window_ms
        or type(overlap_ms) is not int
        or overlap_ms < 0
        or type(padding_ms) is not int
        or padding_ms < 0
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
        windows = _vad_cut_merge(
            total_frames,
            window_frames,
            vad,
            sample_rate * padding_ms // 1000,
            sample_rate * min_window_ms // 1000,
        )
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
            "min_window_ms": min_window_ms if strategy == "vad_cut_merge" else None,
            "overlap_ms": overlap_ms if strategy == "overlap_aware" else 0,
            "padding_ms": padding_ms if strategy == "vad_cut_merge" else 0,
            "source_channels_known": bool(source_channels_known),
        },
        "windows": planned,
        "coverage_ledger": ledger,
        "denominator_policy": "all_source_speech_spans_must_remain_covered",
    }
