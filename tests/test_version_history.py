from services.review.routers.history import (
    note_version_metadata,
    transcript_version_metadata,
)


def test_history_metadata_binds_owner_lineage_source_current_and_approval():
    note = {
        "id": "note-current",
        "version": 2,
        "sha256": "a" * 64,
        "created_at": "2026-01-01T00:00:00Z",
        "body": '{"creator":"clinician-1","transcript_version_id":"tx-1",'
        '"status":"review_required","provenance":{"engine":"local-template-v1"}}',
    }
    current = note_version_metadata(note, None, "note-current")
    assert current["current"] is True
    assert current["owner_clinician_id"] == "clinician-1"
    assert current["transcript_version_id"] == "tx-1"
    assert current["model_lineage"] == "local-template-v1"
    assert current["approval_status"] == "review_required"
    assert current["approved_at"] is None

    approved = note_version_metadata(
        note, {"created_at": "2026-01-02T00:00:00Z"}, "note-later"
    )
    assert approved["current"] is False
    assert approved["approval_status"] == "approved"
    assert approved["approved_at"] == "2026-01-02T00:00:00Z"

    transcript = {
        "id": "tx-1",
        "version": 1,
        "sha256": "b" * 64,
        "created_at": "2026-01-01T00:00:00Z",
        "body": '{"provenance":{"engine":"public-asr-v2"}}',
    }
    source = transcript_version_metadata(transcript, "clinician-1", "tx-1")
    assert source["current"] is True
    assert source["owner_clinician_id"] == "clinician-1"
    assert source["model_lineage"] == "public-asr-v2"
