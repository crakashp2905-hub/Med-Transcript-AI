from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest

from services import domain_contracts as contracts


def test_typed_clinical_boundary_exports_are_present_and_release_safe():
    names = (
        "ClinicalFact",
        "TranscriptVersion",
        "EvidenceSpan",
        "ClaimRelation",
        "VerificationFinding",
        "NoteVersion",
        "InferenceReceipt",
        "Approval",
        "AudioSource",
        "ProcessingConsent",
        "ExportRecord",
    )
    assert all(hasattr(contracts, name) for name in names)
    receipt = contracts.InferenceReceipt(status="completed")
    assert receipt.independent_clinical_gold is False


def test_source_consent_and_export_records_share_typed_versioned_registry():
    now = datetime.now(timezone.utc)
    source = contracts.validate_record(
        "audio_source",
        {
            "id": uuid4(),
            "encounter_id": uuid4(),
            "sha256": "a" * 64,
            "byte_count": 1024,
            "media_type": "audio/wav",
            "state": "sealed",
            "channel_count": 3,
        },
    )
    consent = contracts.validate_record(
        "processing_consent",
        {
            "id": uuid4(),
            "encounter_id": source.encounter_id,
            "scopes": ["recording", "local_processing"],
            "policy_version": "consent_v1",
            "method": "written",
            "granted_at": now,
            "expires_at": now + timedelta(days=1),
        },
    )
    export = contracts.validate_record(
        "export",
        {
            "id": uuid4(),
            "encounter_id": source.encounter_id,
            "approval_id": uuid4(),
            "note_version_id": uuid4(),
            "note_sha256": "b" * 64,
            "transcript_version_id": uuid4(),
            "transcript_sha256": "c" * 64,
            "format": "fhir",
            "artifact_sha256": "d" * 64,
            "created_at": now,
        },
    )
    assert consent.encounter_id == export.encounter_id == source.encounter_id
    assert {
        "audio_source",
        "processing_consent",
        "evidence",
        "fact",
        "relationship",
        "transcript",
        "note",
        "approval",
        "export",
        "inference_receipt",
    } <= set(contracts.MODELS)


def test_processing_consent_rejects_duplicate_scopes_and_naive_timestamps():
    now = datetime.now(timezone.utc)
    body = {
        "id": uuid4(),
        "encounter_id": uuid4(),
        "scopes": ["recording", "recording"],
        "policy_version": "consent_v1",
        "method": "written",
        "granted_at": now,
        "expires_at": now + timedelta(days=1),
    }
    with pytest.raises(ValueError, match="duplicate_processing_consent_scope"):
        contracts.ProcessingConsent.model_validate(body)
    body["scopes"] = ["recording"]
    body["granted_at"] = now.replace(tzinfo=None)
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("processing_consent", body)


def test_note_statements_and_model_receipts_have_typed_source_and_digest_fields():
    segment_id = uuid4()
    statement = contracts.NoteStatement.model_validate(
        {
            "statement_id": uuid4(),
            "text": "Patient reports no cough.",
            "fact_ids": [uuid4()],
            "origin": "source_linked",
            "source_version_id": uuid4(),
            "evidence": {
                "segment_id": segment_id,
                "start_char": 0,
                "end_char": len("Patient reports no cough."),
                "quote": "Patient reports no cough.",
            },
        }
    )
    receipt = contracts.InferenceReceipt(
        status="completed",
        model_digest="a" * 64,
        config_sha256="b" * 64,
        source_sha256="c" * 64,
        duration_ms=12.5,
    )
    assert statement.evidence.segment_id == segment_id
    assert receipt.independent_clinical_gold is False
    with pytest.raises(ValueError):
        contracts.InferenceReceipt(status="completed", model_digest="not-a-hash")
    with pytest.raises(ValueError, match="evidence_span_length_mismatch"):
        contracts.Evidence(
            segment_id=segment_id,
            start_char=0,
            end_char=4,
            quote="words",
        )


def test_typed_records_reject_duplicate_segments_and_unresolved_note_links():
    transcript_id = uuid4()
    encounter_id = uuid4()
    segment_id = uuid4()
    transcript = {
        "id": transcript_id,
        "encounter_id": encounter_id,
        "audio_asset_id": uuid4(),
        "version": 1,
        "duration_ms": 100,
        "segments": [
            {
                "segment_id": segment_id,
                "start_ms": 0,
                "end_ms": 50,
                "text": "Cough",
                "role": "patient",
            },
            {
                "segment_id": segment_id,
                "start_ms": 50,
                "end_ms": 100,
                "text": "Fever",
                "role": "patient",
            },
        ],
    }
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("transcript", transcript)

    fixture = Path(__file__).parent / "fixtures/domain_records/legacy_note_v0.json"
    note = json.loads(fixture.read_text(encoding="utf-8"))
    note["sections"][0]["statements"][0]["fact_ids"] = [str(uuid4())]
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("note", note)


def test_note_statement_ids_and_amendment_parent_references_are_consistent():
    fixture = Path(__file__).parent / "fixtures/domain_records/legacy_note_v0.json"
    note = json.loads(fixture.read_text(encoding="utf-8"))
    note["sections"][0]["statements"][0]["text"] = "Different statement text"
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("note", note)

    note = json.loads(fixture.read_text(encoding="utf-8"))
    duplicate = json.loads(json.dumps(note["sections"][0]["statements"][0]))
    note["sections"].append({"key": "objective", "statements": [duplicate]})
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("note", note)

    note = json.loads(fixture.read_text(encoding="utf-8"))
    note["parent_version_id"] = note["id"]
    with pytest.raises(ValueError, match="invalid_persisted_record_schema"):
        contracts.validate_record("note", note)
