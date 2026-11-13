import hashlib
import json
from pathlib import Path

import pytest

from services.review.routers.history import redacted_synthetic_audit_bundle


def test_synthetic_bundle_keeps_evidence_hashes_and_omits_clinical_text():
    encounter = {
        "body": json.dumps(
            {
                "synthetic_data": True,
                "patient_reference_id": "patient-secret",
            }
        )
    }
    transcript = {
        "version": 2,
        "sha256": "a" * 64,
        "duration_ms": 12345,
        "segments": [
            {"segment_id": "segment-secret", "start_ms": 0, "end_ms": 1000, "text": "source-secret"}
        ],
        "untranscribed_intervals": [],
        "provenance": {"engine": "local-test-engine"},
    }
    note = {
        "version": 1,
        "sha256": "b" * 64,
        "facts": [
            {
                "text": "note-secret",
                "evidence": {
                    "segment_id": "segment-secret",
                    "quote": "quote-secret",
                },
            }
        ],
    }
    bundle = redacted_synthetic_audit_bundle(
        encounter=encounter,
        transcript=transcript,
        note=note,
        verification={"gate": "blocked", "findings": [{"severity": "critical"}]},
        approval=None,
        exports=[{"format": "json", "sha256": "c" * 64}],
        audit_events=[{"time": "2026-11-14T00:00:00Z", "action": "note_saved"}],
    )

    serialized = json.dumps(bundle)
    for secret in (
        "patient-secret",
        "segment-secret",
        "source-secret",
        "note-secret",
        "quote-secret",
    ):
        assert secret not in serialized
    assert bundle["evidence_summary"] == [
        {
            "fact_index": 1,
            "source_segment_ordinal": 1,
            "quote_sha256": hashlib.sha256(b"quote-secret").hexdigest(),
            "source_text_included": False,
        }
    ]
    assert bundle["verification"]["finding_counts_by_severity"] == {"critical": 1}
    assert bundle["approval"]["present"] is False


def test_audit_bundle_refuses_non_synthetic_encounters():
    with pytest.raises(ValueError, match="synthetic_encounter_required"):
        redacted_synthetic_audit_bundle(
            encounter={"body": json.dumps({"synthetic_data": False})},
            transcript=None,
            note=None,
            verification=None,
            approval=None,
            exports=[],
            audit_events=[],
        )


def test_audit_bundle_labels_event_truncation():
    events = [
        {"time": f"2026-11-14T00:{index:03d}Z", "action": "reviewed"}
        for index in range(201)
    ]
    bundle = redacted_synthetic_audit_bundle(
        encounter={"body": json.dumps({"synthetic_data": True})},
        transcript=None,
        note=None,
        verification=None,
        approval=None,
        exports=[],
        audit_events=events,
    )
    assert bundle["audit_event_count"] == 201
    assert bundle["audit_events_truncated"] is True
    assert len(bundle["audit_events"]) == 200


def test_encounter_screen_has_one_click_bundle_download_and_fixture_scope():
    root = Path(__file__).resolve().parents[1]
    hook = (root / "apps/clinician-web/src/hooks/useEncounterWorkspace.ts").read_text(encoding="utf-8")
    app = (root / "apps/clinician-web/src/App.tsx").read_text(encoding="utf-8")
    assert "/audit-bundle" in hook
    assert "Download synthetic audit bundle" in app
    assert "ws.encounter.synthetic_data" in app
