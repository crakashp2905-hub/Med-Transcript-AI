import pytest

from services.asr.segmentation import (
    build_coverage_ledger,
    plan_segments,
    stitch_window_outputs,
)


def test_fixed_and_overlap_plans_cover_source_and_report_duplicates():
    fixed = plan_segments(1000, 1000, "fixed_window", max_window_ms=400)
    overlap = plan_segments(
        1000, 1000, "overlap_aware", max_window_ms=400, overlap_ms=100
    )
    assert fixed["coverage_ledger"]["complete"]
    assert not fixed["coverage_ledger"]["duplicated_source_spans"]
    assert overlap["coverage_ledger"]["complete"]
    assert overlap["coverage_ledger"]["duplicated_source_spans"]


def test_vad_and_pause_aware_windows_preserve_annotated_speech():
    speech = [(100, 200), (350, 420), (700, 900)]
    vad = plan_segments(
        1000,
        1000,
        "vad_cut_merge",
        max_window_ms=300,
        vad_spans=speech,
        speech_spans=speech,
    )
    pause = plan_segments(
        1000,
        1000,
        "pause_aware",
        max_window_ms=400,
        pause_spans=[(240, 300), (600, 650)],
        speech_spans=speech,
    )
    assert vad["coverage_ledger"]["complete"]
    assert pause["coverage_ledger"]["complete"]


def test_channel_first_keeps_channel_ids_without_inventing_source_identity():
    plan = plan_segments(
        1000, 1000, "channel_first", max_window_ms=400, channel_count=2
    )
    assert {row["channel_index"] for row in plan["windows"]} == {0, 1}
    assert not any(row["source_channel_identity_known"] for row in plan["windows"])


def test_vad_plan_rejects_uncovered_speech_and_ledger_identifies_gap():
    with pytest.raises(ValueError, match="segmentation_omitted_source_speech"):
        plan_segments(
            1000,
            1000,
            "vad_cut_merge",
            vad_spans=[(100, 200)],
            speech_spans=[(100, 350)],
        )
    ledger = build_coverage_ledger([(10, 20)], [(10, 15)])
    assert not ledger["complete"]
    assert ledger["missing_source_spans"] == [(15, 20)]


def test_stitch_uses_stable_window_ids_and_only_deduplicates_overlaps():
    plan = plan_segments(
        10000, 1000, "overlap_aware", max_window_ms=4000, overlap_ms=1000
    )
    outputs = [
        {"window_id": row["window_id"], "text": text}
        for row, text in zip(
            plan["windows"],
            (
                "patient takes 5 mg",
                "5 mg daily then stop",
                "then stop tomorrow",
            ),
        )
    ]
    result = stitch_window_outputs(plan, outputs)
    assert result["text"] == "patient takes 5 mg daily then stop tomorrow"
    assert result["review_required"]
    assert [event["removed_tokens"] for event in result["stitch_events"]] == [0, 2, 2]
    assert result["timestamp_kind"] == "window_approximation_only"


def test_stitch_preserves_repetitions_across_non_overlapping_windows():
    plan = plan_segments(8000, 1000, "fixed_window", max_window_ms=4000)
    outputs = [
        {"window_id": plan["windows"][0]["window_id"], "text": "no"},
        {"window_id": plan["windows"][1]["window_id"], "text": "no"},
    ]
    result = stitch_window_outputs(plan, outputs)
    assert result["text"] == "no no"
    assert not result["review_required"]


def test_stitch_rejects_missing_or_duplicate_window_outputs():
    plan = plan_segments(8000, 1000, "fixed_window", max_window_ms=4000)
    first = {"window_id": plan["windows"][0]["window_id"], "text": "one"}
    with pytest.raises(ValueError, match="complete_window_output_set_required"):
        stitch_window_outputs(plan, [first])
