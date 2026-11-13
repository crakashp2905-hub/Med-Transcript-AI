import pytest

from services.review.clinical_models import Extraction, Verdicts


PROTECTED_FIELDS = [
    "reviewed",
    "critical_reviewed",
    "review_status",
    "reviewer_attestation",
    "approval_id",
    "approval_status",
    "owner_clinician_id",
    "clinician_id",
    "evidence_sha256",
    "transcript_sha256",
    "note_sha256",
]


@pytest.mark.parametrize("field", PROTECTED_FIELDS)
def test_extraction_model_output_cannot_set_authority_or_integrity_fields(field):
    from uuid import uuid4

    payload = {
        "facts": [
            {
                "segment_id": str(uuid4()),
                "quote": "Patient denies fever.",
                "category": "symptom",
                "section": "subjective",
            }
        ]
    }
    payload["facts"][0][field] = "attacker-controlled"

    with pytest.raises(ValueError):
        Extraction.model_validate(payload)


@pytest.mark.parametrize("field", PROTECTED_FIELDS)
def test_verifier_model_output_cannot_set_authority_or_integrity_fields(field):
    from uuid import uuid4

    payload = {
        "verdicts": [
            {
                "fact_id": str(uuid4()),
                "label": "supported",
                "evidence_quote": "Patient denies fever.",
                "reason": "The evidence supports the claim.",
            }
        ]
    }
    payload["verdicts"][0][field] = "attacker-controlled"

    with pytest.raises(ValueError):
        Verdicts.model_validate(payload)
