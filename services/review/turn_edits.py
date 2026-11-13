"""Build immutable transcript turn corrections with exact source lineage."""

from uuid import uuid4
from collections import Counter


def build_corrected_segments(source_segments, edits, duration_ms=None):
    source = {str(segment["segment_id"]): segment for segment in source_segments}
    if len(source) != len(source_segments):
        raise ValueError("duplicate_source_segment_id")
    source_order = {segment_id: i for i, segment_id in enumerate(source)}
    covered = set()
    source_intervals = {segment_id: [] for segment_id in source}
    result = []
    previous_start = -1
    for edit in edits:
        values = edit.model_dump(mode="json")
        explicit_id = values.pop("segment_id")
        parent_ids = [str(value) for value in values.pop("parent_segment_ids")]
        if not parent_ids and explicit_id:
            parent_ids = [str(explicit_id)]
        if not parent_ids or len(set(parent_ids)) != len(parent_ids):
            raise ValueError("correction_parent_segments_required")
        if (
            explicit_id
            and str(explicit_id) in source
            and parent_ids != [str(explicit_id)]
        ):
            raise ValueError("correction_identity_lineage_mismatch")
        if any(parent_id not in source for parent_id in parent_ids):
            raise ValueError("correction_parent_segment_unknown")
        ordered_parent_ids = sorted(parent_ids, key=source_order.__getitem__)
        if ordered_parent_ids != parent_ids:
            raise ValueError("correction_parent_order_invalid")
        parent_indexes = [source_order[parent_id] for parent_id in parent_ids]
        if len(parent_indexes) > 1 and parent_indexes != list(
            range(parent_indexes[0], parent_indexes[-1] + 1)
        ):
            raise ValueError("merged_segments_must_be_adjacent")
        parents = [source[parent_id] for parent_id in parent_ids]
        if len(parents) > 1 and (
            len({parent.get("channel_index") for parent in parents}) > 1
            or len({parent.get("role") for parent in parents}) > 1
        ):
            raise ValueError("merged_segments_must_share_channel_and_role")
        start_ms = values.pop("start_ms")
        end_ms = values.pop("end_ms")
        channel_index = values.pop("channel_index")
        start_ms = min(p["start_ms"] for p in parents) if start_ms is None else start_ms
        end_ms = max(p["end_ms"] for p in parents) if end_ms is None else end_ms
        inherited_channels = {p.get("channel_index") for p in parents}
        if channel_index is None:
            if len(inherited_channels) != 1:
                raise ValueError("correction_channel_ambiguous")
            channel_index = next(iter(inherited_channels))
        if (
            type(start_ms) is not int
            or type(end_ms) is not int
            or not 0 <= start_ms < end_ms
            or end_ms > (duration_ms if duration_ms is not None else 3_600_000)
        ):
            raise ValueError("correction_interval_invalid")
        if start_ms < min(p["start_ms"] for p in parents) or end_ms > max(
            p["end_ms"] for p in parents
        ):
            raise ValueError("correction_interval_outside_parent")
        if start_ms < previous_start:
            raise ValueError("correction_segments_must_be_time_ordered")
        previous_start = start_ms
        covered.update(parent_ids)
        for parent_id in parent_ids:
            source_intervals[parent_id].append((start_ms, end_ms))
        base = dict(parents[0])
        new_id = str(uuid4())
        base.update(
            values,
            segment_id=new_id,
            start_ms=start_ms,
            end_ms=end_ms,
            channel_index=channel_index,
            parent_segment_id=parent_ids[0] if len(parent_ids) == 1 else None,
            parent_segment_ids=parent_ids,
        )
        base["role_status"] = (
            "human_confirmed" if base["role"] != "unknown" else "unconfirmed"
        )
        result.append(base)
    if covered != set(source):
        raise ValueError("correction_must_preserve_all_source_segments")
    for parent_id, intervals in source_intervals.items():
        cursor = source[parent_id]["start_ms"]
        for start_ms, end_ms in sorted(intervals):
            if start_ms > cursor:
                break
            cursor = max(cursor, end_ms)
        if cursor < source[parent_id]["end_ms"]:
            raise ValueError("correction_must_preserve_source_interval")
    parent_counts = Counter(
        parent_id for segment in result for parent_id in segment["parent_segment_ids"]
    )
    for segment in result:
        parents = segment["parent_segment_ids"]
        segment["correction_kind"] = (
            "merged_turn"
            if len(parents) > 1
            else "split_child"
            if parent_counts[parents[0]] > 1
            else "reviewed_turn"
        )
    return result
