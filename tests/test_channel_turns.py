import pytest

from services.asr.channel_turns import postprocess_channel_segments


def _segment(segment_id, channel, start, end, text):
    return {
        "segment_id": segment_id,
        "channel_index": channel,
        "speaker_id": f"channel_{channel}",
        "start_ms": start,
        "end_ms": end,
        "text": text,
    }


def test_turn_smoothing_preserves_each_original_timestamp_and_source_id():
    rows = [
        _segment("a", 0, 0, 500, "Hello"),
        _segment("b", 0, 650, 1000, "there"),
        _segment("c", 0, 1500, 1800, "Again"),
    ]

    result = postprocess_channel_segments(rows, duration_ms=2000)

    assert [row["turn_group_id"] for row in result["segments"]] == [
        "channel-0-turn-0",
        "channel-0-turn-0",
        "channel-0-turn-1",
    ]
    assert [(row["start_ms"], row["end_ms"]) for row in result["segments"]] == [
        (0, 500),
        (650, 1000),
        (1500, 1800),
    ]
    assert [row["source_segment_ids"] for row in result["segments"]] == [
        ["a"],
        ["b"],
        ["c"],
    ]


def test_exact_near_aligned_cross_channel_duplicate_is_audited_not_discarded():
    rows = [
        _segment("original", 0, 100, 900, "Take one tablet daily."),
        _segment("duplicate", 1, 120, 920, "TAKE one tablet daily"),
    ]

    result = postprocess_channel_segments(
        rows,
        duration_ms=1000,
        confirmed_duplicate_pairs=[("original", "duplicate")],
    )

    assert [row["segment_id"] for row in result["segments"]] == ["original"]
    assert result["suppressed_segments"][0]["segment_id"] == "duplicate"
    assert result["suppressed_segments"][0]["requires_human_review"] is True
    assert result["suppressed_segments"][0]["suppressed_by_segment_id"] == "original"
    assert result["processing_log"][1]["source_start_ms"] == 120
    assert result["processing_log"][1]["source_end_ms"] == 920


def test_unconfirmed_duplicate_candidate_stays_in_primary_segments():
    result = postprocess_channel_segments(
        [
            _segment("original", 0, 100, 900, "Take one tablet daily."),
            _segment("possible", 1, 120, 920, "Take one tablet daily."),
        ],
        duration_ms=1000,
    )

    assert len(result["segments"]) == 2
    assert result["suppressed_segments"] == []
    assert result["duplicate_candidates"] == [
        {
            "segment_id": "possible",
            "candidate_duplicate_of_segment_id": "original",
            "requires_human_review": True,
        }
    ]


def test_different_text_and_time_are_never_suppressed_as_duplicates():
    result = postprocess_channel_segments(
        [
            _segment("a", 0, 0, 300, "yes"),
            _segment("b", 1, 500, 800, "yes"),
            _segment("c", 1, 0, 300, "no"),
        ],
        duration_ms=1000,
    )

    assert len(result["segments"]) == 3
    assert result["suppressed_segments"] == []


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (
            {
                "segment_id": "x",
                "channel_index": 0,
                "start_ms": 2,
                "end_ms": 1,
                "text": "bad",
            },
            "invalid_source_aligned_channel_segment",
        ),
        (
            {
                "segment_id": "x",
                "channel_index": 0,
                "start_ms": 0,
                "end_ms": 1,
                "text": " ",
            },
            "invalid_source_aligned_channel_segment",
        ),
    ],
)
def test_invalid_timestamps_or_empty_text_fail_closed(row, message):
    with pytest.raises(ValueError, match=message):
        postprocess_channel_segments([row], duration_ms=100)
