"""Source-aligned channel turn smoothing and conservative duplicate suppression."""

import re
import unicodedata


def _normalized_text(value):
    folded = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"\w+", folded, flags=re.UNICODE))


def postprocess_channel_segments(
    segments,
    *,
    duration_ms,
    max_turn_gap_ms=250,
    duplicate_overlap_ratio=0.95,
    duplicate_boundary_tolerance_ms=100,
):
    """Group nearby same-channel turns and isolate exact cross-channel duplicates.

    The returned log keeps every original segment ID, time range and channel.
    Suppressed duplicates remain available in a separate audit list and require
    clinician review; this function does not assign clinical speaker roles.
    """
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("invalid_channel_turn_duration")
    if type(max_turn_gap_ms) is not int or max_turn_gap_ms < 0:
        raise ValueError("invalid_channel_turn_gap")
    if (
        isinstance(duplicate_overlap_ratio, bool)
        or not isinstance(duplicate_overlap_ratio, (int, float))
        or not 0 < duplicate_overlap_ratio <= 1
    ):
        raise ValueError("invalid_duplicate_overlap_ratio")
    if (
        type(duplicate_boundary_tolerance_ms) is not int
        or duplicate_boundary_tolerance_ms < 0
    ):
        raise ValueError("invalid_duplicate_boundary_tolerance")

    normalized = []
    seen_ids = set()
    for index, original in enumerate(segments):
        segment = dict(original)
        start, end = segment.get("start_ms"), segment.get("end_ms")
        channel = segment.get("channel_index")
        segment_id = segment.get("segment_id")
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= duration_ms
            or type(channel) is not int
            or channel < 0
            or not isinstance(segment.get("text"), str)
            or not segment["text"].strip()
            or not isinstance(segment_id, str)
            or not segment_id
            or segment_id in seen_ids
        ):
            raise ValueError("invalid_source_aligned_channel_segment")
        seen_ids.add(segment_id)
        segment["source_segment_ids"] = [segment_id]
        normalized.append(segment)

    # Form smoothed turns without changing the source segment timestamps.
    by_channel = {}
    for segment in sorted(
        normalized,
        key=lambda row: (row["channel_index"], row["start_ms"], row["end_ms"]),
    ):
        by_channel.setdefault(segment["channel_index"], []).append(segment)
    for channel, rows in by_channel.items():
        turn_index = -1
        prior_end = None
        for row in rows:
            if prior_end is None or row["start_ms"] - prior_end > max_turn_gap_ms:
                turn_index += 1
            row["turn_group_id"] = f"channel-{channel}-turn-{turn_index}"
            prior_end = max(prior_end or 0, row["end_ms"])

    ordered = sorted(
        normalized,
        key=lambda row: (row["start_ms"], row["end_ms"], row["channel_index"]),
    )
    suppressed = {}
    by_text = {}
    for row in ordered:
        key = _normalized_text(row["text"])
        if not key:
            continue
        for prior in by_text.get(key, []):
            if prior["channel_index"] == row["channel_index"]:
                continue
            overlap = max(
                0,
                min(prior["end_ms"], row["end_ms"])
                - max(prior["start_ms"], row["start_ms"]),
            )
            shorter = min(
                prior["end_ms"] - prior["start_ms"],
                row["end_ms"] - row["start_ms"],
            )
            if (
                shorter > 0
                and overlap / shorter >= duplicate_overlap_ratio
                and abs(prior["start_ms"] - row["start_ms"])
                <= duplicate_boundary_tolerance_ms
                and abs(prior["end_ms"] - row["end_ms"])
                <= duplicate_boundary_tolerance_ms
            ):
                # Prefer the earlier source turn deterministically; retain the
                # duplicate with full provenance for review and correction.
                suppressed[row["segment_id"]] = prior["segment_id"]
                if "duplicate_channel_source_segment_ids" in prior:
                    prior["duplicate_channel_source_segment_ids"].append(
                        row["segment_id"]
                    )
                else:
                    prior["duplicate_channel_source_segment_ids"] = [
                        prior["segment_id"],
                        row["segment_id"],
                    ]
                break
        else:
            by_text.setdefault(key, []).append(row)

    retained = []
    suppressed_rows = []
    processing_log = []
    for row in ordered:
        action = "retained"
        details = {}
        if row["segment_id"] in suppressed:
            action = "suppressed_cross_channel_duplicate_for_review"
            details = {
                "suppressed_by_segment_id": suppressed[row["segment_id"]],
                "requires_human_review": True,
            }
            suppressed_rows.append({**row, **details})
        else:
            retained.append(row)
        processing_log.append(
            {
                "segment_id": row["segment_id"],
                "source_segment_ids": row["source_segment_ids"],
                "channel_index": row["channel_index"],
                "source_start_ms": row["start_ms"],
                "source_end_ms": row["end_ms"],
                "action": action,
                **details,
            }
        )
    return {
        "segments": retained,
        "suppressed_segments": suppressed_rows,
        "processing_log": processing_log,
        "turn_grouping_max_gap_ms": max_turn_gap_ms,
        "duplicate_overlap_ratio": duplicate_overlap_ratio,
        "duplicate_boundary_tolerance_ms": duplicate_boundary_tolerance_ms,
    }
