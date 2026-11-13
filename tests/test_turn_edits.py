from uuid import uuid4

import pytest

from services.review.models import SegmentEdit
from services.review.turn_edits import build_corrected_segments


def source_segments():
    first, second = str(uuid4()), str(uuid4())
    return [
        {
            "segment_id": first,
            "start_ms": 0,
            "end_ms": 500,
            "text": "Hello",
            "role": "patient",
            "channel_index": 0,
        },
        {
            "segment_id": second,
            "start_ms": 500,
            "end_ms": 1000,
            "text": "there",
            "role": "patient",
            "channel_index": 0,
        },
    ]


def test_split_children_keep_audio_channel_and_parent_lineage():
    source = source_segments()
    parent_id = source[0]["segment_id"]
    edits = [
        SegmentEdit(
            parent_segment_ids=[parent_id],
            start_ms=0,
            end_ms=200,
            text="Hel",
            role="patient",
            channel_index=0,
        ),
        SegmentEdit(
            parent_segment_ids=[parent_id],
            start_ms=200,
            end_ms=500,
            text="lo",
            role="patient",
            channel_index=0,
        ),
        SegmentEdit(segment_id=source[1]["segment_id"], text="there", role="patient"),
    ]
    result = build_corrected_segments(source, edits, duration_ms=1000)
    assert [row["correction_kind"] for row in result] == [
        "split_child",
        "split_child",
        "reviewed_turn",
    ]
    assert all(row["parent_segment_ids"] == [parent_id] for row in result[:2])
    assert all(row["channel_index"] == 0 for row in result)
    assert len({row["segment_id"] for row in result}) == len(result)


def test_merge_requires_adjacent_same_role_same_channel_and_preserves_both_parents():
    source = source_segments()
    edit = SegmentEdit(
        parent_segment_ids=[row["segment_id"] for row in source],
        start_ms=0,
        end_ms=1000,
        text="Hello there",
        role="patient",
        channel_index=0,
    )
    result = build_corrected_segments(source, [edit], duration_ms=1000)
    assert result[0]["correction_kind"] == "merged_turn"
    assert result[0]["parent_segment_ids"] == [row["segment_id"] for row in source]


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("omit", "correction_must_preserve_all_source_segments"),
        ("channel", "merged_segments_must_share_channel_and_role"),
        ("bounds", "correction_interval_invalid"),
        ("interval_gap", "correction_must_preserve_source_interval"),
        ("nonadjacent", "merged_segments_must_be_adjacent"),
    ],
)
def test_invalid_turn_corrections_fail_closed(mutation, code):
    source = source_segments()
    if mutation == "omit":
        edits = [
            SegmentEdit(
                segment_id=source[0]["segment_id"], text="Hello", role="patient"
            )
        ]
    elif mutation == "channel":
        source[1]["channel_index"] = 1
        edits = [
            SegmentEdit(
                parent_segment_ids=[row["segment_id"] for row in source],
                start_ms=0,
                end_ms=1000,
                text="Hello there",
                role="patient",
            )
        ]
    elif mutation == "bounds":
        edits = [
            SegmentEdit(
                segment_id=source[0]["segment_id"],
                start_ms=0,
                end_ms=1001,
                text="Hello",
                role="patient",
            )
        ]
        edits.append(
            SegmentEdit(
                segment_id=source[1]["segment_id"], text="there", role="patient"
            )
        )
    elif mutation == "interval_gap":
        edits = [
            SegmentEdit(
                segment_id=source[0]["segment_id"],
                start_ms=0,
                end_ms=400,
                text="Hello",
                role="patient",
            ),
            SegmentEdit(
                segment_id=source[1]["segment_id"], text="there", role="patient"
            ),
        ]
    else:
        third = dict(source[1], segment_id=str(uuid4()), start_ms=1000, end_ms=1500)
        source.append(third)
        edits = [
            SegmentEdit(
                parent_segment_ids=[source[0]["segment_id"], third["segment_id"]],
                start_ms=0,
                end_ms=1500,
                text="Hello there",
                role="patient",
                channel_index=0,
            ),
            SegmentEdit(
                segment_id=source[1]["segment_id"], text="there", role="patient"
            ),
        ]
    with pytest.raises(ValueError, match=code):
        build_corrected_segments(source, edits, duration_ms=1000)
