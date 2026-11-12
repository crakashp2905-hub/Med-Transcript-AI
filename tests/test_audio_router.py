import copy

import pytest

from services.asr.audio_router import (
    build_routing_plan,
    route_quality,
    validate_routing_conservation,
)


def quality(**updates):
    report = {
        "schema_version": "audio_quality_v1",
        "audio_sha256": "a" * 64,
        "duration_ms": 1000,
        "clipping_fraction": 0,
        "silence_fraction": 0.2,
        "channel_imbalance_db": None,
        "sample_jump_count": 0,
        "snr_status": "not_measured_reference_spans_required",
        "snr_db": None,
    }
    report.update(updates)
    return report


def test_clean_route_is_not_a_confidence_and_keeps_source_required():
    route = route_quality(quality())
    assert route["route_candidate"] == "standard_candidate"
    assert route["score_kind"] == "uncalibrated_deterministic_quality_heuristic"
    assert route["confidence"] is None
    assert route["source_audio_required"] is True
    assert route["full_content_required"] is True


def test_adverse_quality_routes_to_review_with_explicit_reasons():
    route = route_quality(
        quality(
            clipping_fraction=0.01,
            silence_fraction=0.98,
            channel_imbalance_db=20,
            sample_jump_count=40,
            snr_status="estimated_from_caller_labeled_spans",
            snr_db=8.0,
        )
    )
    assert route["route_candidate"] == "review_required"
    assert set(route["reasons"]) == {
        "clipping_above_threshold",
        "very_high_silence_fraction",
        "channel_imbalance_above_threshold",
        "sample_jump_rate_above_threshold",
        "labeled_snr_below_threshold",
    }
    assert route["may_remove_audio_or_reference_words"] is False


def test_unlabeled_snr_cannot_drive_route():
    with pytest.raises(ValueError, match="unlabeled_snr_must_not_drive_routing"):
        route_quality(quality(snr_db=3.0))


def test_routing_plan_preserves_all_case_ids_and_reference_words():
    source_rows = [
        {"sample_id": "one", "reference_words": 8, "audio_quality": quality()},
        {
            "sample_id": "two",
            "reference_words": 6,
            "audio_quality": quality(clipping_fraction=0.02),
        },
    ]
    plan = build_routing_plan(source_rows)
    assert validate_routing_conservation(source_rows, plan)
    assert plan["sample_count"] == 2
    assert plan["reference_words"] == 14
    assert [row["route"]["route_candidate"] for row in plan["samples"]] == [
        "standard_candidate",
        "review_required",
    ]

    altered = copy.deepcopy(plan)
    altered["samples"].pop()
    altered["sample_count"] -= 1
    altered["reference_words"] -= 6
    with pytest.raises(
        ValueError, match="audio_routing_changed_evaluation_denominator"
    ):
        validate_routing_conservation(source_rows, altered)
