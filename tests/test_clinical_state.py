from uuid import uuid4

import pytest

from services.asr.profiles import content_sha256
from services.review.clinical_state import compare_snapshots, freeze_snapshot


def source(text):
    return {
        "id": str(uuid4()),
        "segments": [{"segment_id": str(uuid4()), "text": text}],
    }


def fact(transcript, *, text, **attributes):
    segment = transcript["segments"][0]
    start = segment["text"].index(text)
    return {
        "fact_id": str(uuid4()),
        "category": "symptom",
        "concept": "fever",
        "subject": "patient",
        "assertion": "affirmed",
        "temporality": "current",
        "reviewed": False,
        "critical_reviewed": False,
        **attributes,
        "evidence": {
            "segment_id": segment["segment_id"],
            "start_char": start,
            "end_char": start + len(text),
            "quote": text,
        },
    }


def freeze(transcript, facts):
    return freeze_snapshot(transcript, content_sha256(transcript), facts)


def test_successive_transcript_versions_flag_opposite_assertions_with_both_sources():
    before = source("Patient reports fever.")
    after = source("Patient denies fever.")
    previous = freeze(before, [fact(before, text="Patient reports fever.")])
    current = freeze(
        after,
        [fact(after, text="Patient denies fever.", assertion="negated")],
    )

    result = compare_snapshots(previous, current)

    assert result["status"] == "review_required"
    assert result["changes"][0]["change"] == "potential_contradiction"
    assert result["changes"][0]["severity"] == "critical"
    assert result["changes"][0]["requires_clinician_review"] is True
    assert (
        result["changes"][0]["previous_evidence"]["segment_id"]
        == before["segments"][0]["segment_id"]
    )
    assert (
        result["changes"][0]["current_evidence"]["segment_id"]
        == after["segments"][0]["segment_id"]
    )
    assert result["approval_authority"] is False


def test_measurement_or_medication_attribute_change_is_reviewed_not_resolved():
    before = source("Taking warfarin.")
    after = source("Taking warfarin.")
    old_fact = fact(
        before,
        text="Taking warfarin.",
        category="medication",
        concept="warfarin",
        medication_name="warfarin",
        dose_value="2.5",
        dose_unit="mg",
    )
    new_fact = fact(
        after,
        text="Taking warfarin.",
        category="medication",
        concept="warfarin",
        medication_name="warfarin",
        dose_value="5",
        dose_unit="mg",
    )

    result = compare_snapshots(freeze(before, [old_fact]), freeze(after, [new_fact]))

    assert result["changes"][0]["change"] == "clinical_state_changed"
    assert result["changes"][0]["changed_fields"] == ["dose_value"]
    assert result["changes"][0]["severity"] == "major"
    assert result["clinical_truth_established"] is False


def test_snapshot_integrity_and_source_evidence_are_required():
    transcript = source("Patient reports fever.")
    snapshot = freeze(transcript, [fact(transcript, text="Patient reports fever.")])
    tampered = {**snapshot, "facts": []}
    next_version = source("Patient denies fever.")
    next_snapshot = freeze(
        next_version,
        [fact(next_version, text="Patient denies fever.", assertion="negated")],
    )
    with pytest.raises(ValueError, match="clinical_state_snapshot_integrity_failure"):
        compare_snapshots(tampered, next_snapshot)

    invalid = fact(transcript, text="Patient reports fever.")
    invalid["evidence"]["quote"] = "fabricated"
    with pytest.raises(ValueError, match="clinical_state_evidence_span_invalid"):
        freeze(transcript, [invalid])
