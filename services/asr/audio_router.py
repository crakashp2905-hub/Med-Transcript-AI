"""Versioned quality routing heuristic that never drops source audio or cases."""

import hashlib
import json


ROUTING_PROFILE = {
    "schema_version": "audio_quality_route_v1",
    "profile_id": "deterministic_quality_flags_v1",
    "maximum_clipping_fraction": 0.001,
    "maximum_silence_fraction": 0.95,
    "maximum_channel_imbalance_db": 12.0,
    "maximum_sample_jumps_per_second": 20.0,
    "minimum_labeled_snr_db": 12.0,
}


def _digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def route_quality(quality_report, profile=ROUTING_PROFILE):
    """Classify measured quality flags; this is not confidence or a transcript gate."""
    if profile != ROUTING_PROFILE:
        raise ValueError("unsupported_audio_routing_profile")
    if (
        not isinstance(quality_report, dict)
        or quality_report.get("schema_version") != "audio_quality_v1"
        or not isinstance(quality_report.get("audio_sha256"), str)
        or len(quality_report["audio_sha256"]) != 64
    ):
        raise ValueError("versioned_audio_quality_report_required")
    duration_ms = quality_report.get("duration_ms")
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("audio_quality_duration_required")

    reasons = []
    clipping = quality_report.get("clipping_fraction")
    silence = quality_report.get("silence_fraction")
    imbalance = quality_report.get("channel_imbalance_db")
    jumps = quality_report.get("sample_jump_count")
    if type(clipping) not in (int, float) or not 0 <= clipping <= 1:
        raise ValueError("invalid_audio_clipping_metric")
    if type(silence) not in (int, float) or not 0 <= silence <= 1:
        raise ValueError("invalid_audio_silence_metric")
    if type(jumps) is not int or jumps < 0:
        raise ValueError("invalid_audio_sample_jump_metric")

    if clipping > profile["maximum_clipping_fraction"]:
        reasons.append("clipping_above_threshold")
    if silence > profile["maximum_silence_fraction"]:
        reasons.append("very_high_silence_fraction")
    if imbalance is not None:
        if type(imbalance) not in (int, float) or imbalance < 0:
            raise ValueError("invalid_audio_channel_imbalance_metric")
        if imbalance > profile["maximum_channel_imbalance_db"]:
            reasons.append("channel_imbalance_above_threshold")
    jump_rate = jumps * 1000 / duration_ms
    if jump_rate > profile["maximum_sample_jumps_per_second"]:
        reasons.append("sample_jump_rate_above_threshold")

    snr_status = quality_report.get("snr_status", "not_measured")
    snr_db = quality_report.get("snr_db")
    if snr_status == "estimated_from_caller_labeled_spans":
        if type(snr_db) not in (int, float):
            raise ValueError("labeled_snr_value_required")
        if snr_db < profile["minimum_labeled_snr_db"]:
            reasons.append("labeled_snr_below_threshold")
    elif snr_db is not None:
        raise ValueError("unlabeled_snr_must_not_drive_routing")

    return {
        "schema_version": profile["schema_version"],
        "profile_id": profile["profile_id"],
        "profile_sha256": _digest(profile),
        "audio_sha256": quality_report["audio_sha256"],
        "route_candidate": "review_required" if reasons else "standard_candidate",
        "reasons": reasons,
        "score_kind": "uncalibrated_deterministic_quality_heuristic",
        "confidence": None,
        "source_audio_required": True,
        "full_content_required": True,
        "may_remove_audio_or_reference_words": False,
    }


def build_routing_plan(rows):
    """Route all evaluation cases and prove IDs/word denominators are conserved."""
    plan = []
    seen = set()
    reference_words = 0
    for row in rows:
        sample_id = row.get("sample_id")
        words = row.get("reference_words")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError("unique_evaluation_sample_id_required")
        if type(words) is not int or words < 0:
            raise ValueError("valid_reference_word_count_required")
        seen.add(sample_id)
        reference_words += words
        route = route_quality(row.get("audio_quality"))
        plan.append(
            {
                "sample_id": sample_id,
                "reference_words": words,
                "route": route,
            }
        )
    return {
        "schema_version": "audio_quality_routing_plan_v1",
        "candidate_profile_sha256": _digest(ROUTING_PROFILE),
        "sample_count": len(plan),
        "reference_words": reference_words,
        "samples": plan,
        "denominator_policy": "every_input_case_and_reference_word_is_retained",
    }


def validate_routing_conservation(source_rows, plan):
    expected = [
        (row.get("sample_id"), row.get("reference_words")) for row in source_rows
    ]
    actual = [
        (row.get("sample_id"), row.get("reference_words"))
        for row in plan.get("samples", [])
    ]
    if (
        plan.get("sample_count") != len(source_rows)
        or actual != expected
        or plan.get("reference_words") != sum(words for _, words in expected)
    ):
        raise ValueError("audio_routing_changed_evaluation_denominator")
    return True
