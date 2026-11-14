import re
from pathlib import Path

from services.api.contracts import (
    AuthorizationInput,
    EncounterInput,
    TranscriptionInput,
    UploadInput,
)
from services.review.models import (
    ApprovalInput,
    Evidence,
    ExportInput,
    Fact,
    FactRelation,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/product-architecture.md"


def test_architecture_spec_references_existing_modules_and_typed_contracts():
    text = SPEC.read_text(encoding="utf-8")
    referenced = re.findall(r"`((?:apps|services)/[^`]+\.(?:py|ts|tsx))`", text)
    assert len(referenced) >= 20
    assert all((ROOT / path).is_file() for path in referenced)
    for name in (
        "EncounterInput",
        "AuthorizationInput",
        "UploadInput",
        "TranscriptionInput",
        "Evidence",
        "FactRelation",
        "Fact",
        "ApprovalInput",
        "ExportInput",
    ):
        assert name in text

    assert set(EncounterInput.model_fields) >= {
        "patient_reference_id",
        "patient_identifiers_confirmed",
        "language",
        "synthetic_data",
    }
    assert set(AuthorizationInput.model_fields) >= {
        "scopes",
        "policy_version",
        "method",
        "expires_at",
    }
    assert set(UploadInput.model_fields) >= {"bytes", "sha256", "media_type"}
    assert "audio_asset_id" in TranscriptionInput.model_fields
    assert set(Evidence.model_fields) >= {
        "segment_id",
        "start_char",
        "end_char",
        "quote",
    }
    assert "related_fact_id" in FactRelation.model_fields
    assert set(Fact.model_fields) >= {"assertion", "subject", "temporality", "evidence"}
    assert "expected_note_sha256" in ApprovalInput.model_fields
    assert "format" in ExportInput.model_fields
