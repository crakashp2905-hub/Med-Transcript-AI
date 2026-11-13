from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.domain_contracts import NoteVersion
from services.review.models import Fact


def manual_fact(**overrides):
    return {
        "fact_id": uuid4(),
        "category": "other",
        "section": "subjective",
        "text": "Clinician confirmed prior dose by label.",
        "origin": "manual_no_audio_evidence",
        "source_modality": "manual_no_audio_evidence",
        "owner_clinician_id": uuid4(),
        "evidence": None,
        "clarification": "Confirmed directly against the medication label.",
        **overrides,
    }


def test_manual_fact_has_separate_source_and_owner_provenance():
    fact = Fact.model_validate(manual_fact())

    assert fact.origin == "manual_no_audio_evidence"
    assert fact.source_modality == "manual_no_audio_evidence"
    assert fact.owner_clinician_id is not None
    assert fact.evidence is None
    assert fact.review_status == "unreviewed"


@pytest.mark.parametrize(
    "changes",
    [
        {"owner_clinician_id": None},
        {"source_modality": "transcript"},
        {
            "evidence": {
                "segment_id": str(uuid4()),
                "start_char": 0,
                "end_char": 4,
                "quote": "text",
            }
        },
        {"clarification": "too short"},
    ],
)
def test_manual_fact_rejects_missing_or_conflicting_provenance(changes):
    with pytest.raises(ValidationError):
        Fact.model_validate(manual_fact(**changes))


def test_manual_source_label_cannot_be_attached_to_a_source_linked_fact():
    with pytest.raises(ValidationError, match="manual_fact_provenance_mismatch"):
        Fact.model_validate(
            manual_fact(
                origin="source_linked",
                evidence={
                    "segment_id": str(uuid4()),
                    "start_char": 0,
                    "end_char": 4,
                    "quote": "text",
                },
            )
        )


def test_note_statement_retains_manual_fact_owner():
    fact = Fact.model_validate(manual_fact())
    note = NoteVersion.model_validate(
        {
            "id": uuid4(),
            "encounter_id": uuid4(),
            "version": 1,
            "transcript_version_id": uuid4(),
            "transcript_sha256": "a" * 64,
            "verification_report_id": uuid4(),
            "facts": [fact.model_dump()],
            "sections": [
                {
                    "key": "subjective",
                    "statements": [
                        {
                            "statement_id": uuid4(),
                            "text": fact.text,
                            "fact_ids": [fact.fact_id],
                            "origin": "manual_no_audio_evidence",
                            "owner_clinician_id": fact.owner_clinician_id,
                        }
                    ],
                }
            ],
        }
    )

    assert note.sections[0].statements[0].owner_clinician_id == fact.owner_clinician_id


def test_note_statement_cannot_change_manual_fact_owner():
    fact = Fact.model_validate(manual_fact())
    note = {
        "id": uuid4(),
        "encounter_id": uuid4(),
        "version": 1,
        "transcript_version_id": uuid4(),
        "transcript_sha256": "a" * 64,
        "verification_report_id": uuid4(),
        "facts": [fact.model_dump()],
        "sections": [
            {
                "key": "subjective",
                "statements": [
                    {
                        "statement_id": uuid4(),
                        "text": fact.text,
                        "fact_ids": [fact.fact_id],
                        "origin": "manual_no_audio_evidence",
                        "owner_clinician_id": uuid4(),
                    }
                ],
            }
        ],
    }

    with pytest.raises(ValidationError, match="note_statement_owner_mismatch"):
        NoteVersion.model_validate(note)
