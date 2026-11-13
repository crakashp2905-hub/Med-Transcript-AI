"""Immutable source-bound snapshots for comparing clinical proposals over time."""

from collections import defaultdict
import re

from services.asr.profiles import content_sha256


SNAPSHOT_SCHEMA = "clinical_state_snapshot_v1"
CLINICAL_FIELDS = (
    "category",
    "concept",
    "anatomical_site",
    "laterality",
    "subject",
    "assertion",
    "temporality",
    "medication_name",
    "dose_value",
    "dose_unit",
    "route",
    "frequency",
    "duration",
    "allergen",
    "allergy_reaction",
    "measurement_value",
    "measurement_unit",
)


def _key(fact):
    explicit = (
        fact.get("medication_name")
        or fact.get("allergen")
        or fact.get("concept")
        or fact.get("text")
    )
    tokens = re.sub(r"\W+", " ", str(explicit).casefold()).split()
    tokens = [
        token
        for token in tokens
        if token
        not in {
            "a",
            "an",
            "and",
            "denies",
            "deny",
            "denied",
            "experiences",
            "experiencing",
            "has",
            "have",
            "had",
            "is",
            "no",
            "not",
            "of",
            "patient",
            "reports",
            "report",
            "reported",
            "the",
            "was",
            "with",
            "without",
        }
    ]
    normalized = " ".join(tokens) or f"fact:{fact.get('fact_id', '')}"
    return content_sha256(
        {
            "category": fact.get("category", "other"),
            "subject": fact.get("subject", "unknown"),
            "key": normalized,
        }
    )


def _verify_snapshot(snapshot):
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema_version") != SNAPSHOT_SCHEMA
    ):
        raise ValueError("clinical_state_snapshot_schema_invalid")
    claimed = snapshot.get("snapshot_sha256")
    body = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    if not isinstance(claimed, str) or content_sha256(body) != claimed:
        raise ValueError("clinical_state_snapshot_integrity_failure")


def freeze_snapshot(transcript, transcript_sha256, facts):
    """Freeze extracted clinical facts with exact source offsets and no review flags."""
    if content_sha256(transcript) != transcript_sha256:
        raise ValueError("clinical_state_transcript_hash_mismatch")
    segments = {str(row["segment_id"]): row for row in transcript.get("segments", [])}
    frozen = []
    for fact in facts:
        if fact.get("reviewed") or fact.get("critical_reviewed"):
            raise ValueError("clinical_state_model_fact_cannot_be_reviewed")
        evidence = fact.get("evidence") or {}
        segment = segments.get(str(evidence.get("segment_id")))
        quote = evidence.get("quote")
        start, end = evidence.get("start_char"), evidence.get("end_char")
        if (
            segment is None
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(segment.get("text", ""))
            or segment["text"][start:end] != quote
        ):
            raise ValueError("clinical_state_evidence_span_invalid")
        attributes = {field: fact.get(field) for field in CLINICAL_FIELDS}
        frozen.append(
            {
                "fact_id": str(fact["fact_id"]),
                "concept_key_sha256": _key(fact),
                "attributes": attributes,
                "evidence": {
                    "segment_id": str(evidence["segment_id"]),
                    "start_char": start,
                    "end_char": end,
                    "quote_sha256": content_sha256(quote),
                },
                "review_status": "unreviewed",
            }
        )
    frozen.sort(
        key=lambda row: (
            row["evidence"]["segment_id"],
            row["evidence"]["start_char"],
            row["fact_id"],
        )
    )
    body = {
        "schema_version": SNAPSHOT_SCHEMA,
        "transcript_version_id": str(transcript["id"]),
        "transcript_sha256": transcript_sha256,
        "facts": frozen,
        "clinical_accuracy": "not_established",
        "approval_authority": False,
    }
    return {**body, "snapshot_sha256": content_sha256(body)}


def compare_snapshots(previous, current):
    """Flag changed source-linked states; never decide which transcript is true."""
    _verify_snapshot(previous)
    _verify_snapshot(current)
    if previous["transcript_version_id"] == current["transcript_version_id"]:
        raise ValueError("clinical_state_snapshot_source_must_advance")
    old_groups, new_groups = defaultdict(list), defaultdict(list)
    for fact in previous["facts"]:
        old_groups[fact["concept_key_sha256"]].append(fact)
    for fact in current["facts"]:
        new_groups[fact["concept_key_sha256"]].append(fact)
    changes = []
    for key in old_groups.keys() & new_groups.keys():
        for before in old_groups[key]:
            for after in new_groups[key]:
                changed = [
                    name
                    for name in CLINICAL_FIELDS
                    if before["attributes"].get(name) != after["attributes"].get(name)
                ]
                if not changed:
                    continue
                old_assertion = before["attributes"].get("assertion")
                new_assertion = after["attributes"].get("assertion")
                direct_opposition = {old_assertion, new_assertion} == {
                    "affirmed",
                    "negated",
                }
                changes.append(
                    {
                        "change": "potential_contradiction"
                        if direct_opposition
                        else "clinical_state_changed",
                        "severity": "critical" if direct_opposition else "major",
                        "changed_fields": changed,
                        "previous_fact_id": before["fact_id"],
                        "current_fact_id": after["fact_id"],
                        "previous_evidence": before["evidence"],
                        "current_evidence": after["evidence"],
                        "requires_clinician_review": True,
                    }
                )
    return {
        "schema_version": "clinical_state_comparison_v1",
        "status": "review_required" if changes else "no_matched_state_change_detected",
        "previous_snapshot_sha256": previous["snapshot_sha256"],
        "current_snapshot_sha256": current["snapshot_sha256"],
        "changes": changes,
        "unmatched_previous_fact_count": sum(
            len(rows) for key, rows in old_groups.items() if key not in new_groups
        ),
        "unmatched_current_fact_count": sum(
            len(rows) for key, rows in new_groups.items() if key not in old_groups
        ),
        "model_verdicts_ignored": True,
        "clinical_truth_established": False,
        "approval_authority": False,
    }


def proposal_state(transcript, transcript_sha256, facts, previous_snapshot=None):
    current = freeze_snapshot(transcript, transcript_sha256, facts)
    if previous_snapshot is None:
        comparison = {
            "schema_version": "clinical_state_comparison_v1",
            "status": "baseline_snapshot_no_comparable_prior",
            "previous_snapshot_sha256": None,
            "current_snapshot_sha256": current["snapshot_sha256"],
            "changes": [],
            "model_verdicts_ignored": True,
            "clinical_truth_established": False,
            "approval_authority": False,
        }
    else:
        comparison = compare_snapshots(previous_snapshot, current)
    return current, comparison
