from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def unicode_text(cls, value):
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise ValueError("Valid Unicode text is required") from None
        return value


class Evidence(Strict):
    segment_id: UUID
    start_char: int = Field(ge=0, strict=True)
    end_char: int = Field(ge=1, strict=True)
    quote: str = Field(min_length=1, max_length=4000)


class Fact(Strict):
    fact_id: UUID
    category: Literal["symptom", "medication", "allergy", "measurement", "assessment", "plan", "other"] = "other"
    section: Literal["subjective", "objective", "assessment", "plan"] = "subjective"
    text: str = Field(min_length=1, max_length=4000)
    subject: Literal["patient", "family", "caregiver", "other", "unknown"] = "unknown"
    assertion: Literal["affirmed", "negated", "uncertain", "not_stated"] = "uncertain"
    temporality: Literal["current", "historical", "planned", "unknown"] = "unknown"
    origin: Literal["source_linked", "clinician_entered"] = "source_linked"
    evidence: Evidence | None = None
    reviewed: bool = False
    critical_reviewed: bool = False
    clarification: str = Field(default="", max_length=2000)
    excluded: bool = False

    @model_validator(mode="after")
    def provenance(self):
        if self.origin == "source_linked" and self.evidence is None:
            raise ValueError("Source-linked facts require evidence")
        if self.origin == "clinician_entered" and (self.evidence is not None or len(self.clarification.strip()) < 10):
            raise ValueError("Clinician additions require a reason and cannot invent source evidence")
        self.text.encode("utf-8")
        return self


class DraftInput(Strict):
    transcript_version_id: UUID
    facts: list[Fact] = Field(min_length=1, max_length=300)


class NoteEdit(DraftInput):
    amendment_reason: str = Field(default="", max_length=2000)


class SegmentEdit(Strict):
    segment_id: UUID
    text: str = Field(max_length=4000)
    role: Literal["patient", "clinician", "caregiver", "unknown"] = "unknown"


class ReviewAttestation(Strict):
    english_confirmed: bool = False
    source_completeness_reviewed: bool = False
    source_review_reason: str = Field(default="", max_length=2000)


class TranscriptEdit(ReviewAttestation):
    segments: list[SegmentEdit] = Field(max_length=10000)
    correction_reason: str = Field(min_length=10, max_length=2000)


class ManualSegment(Strict):
    start_ms: int = Field(ge=0, strict=True)
    end_ms: int = Field(gt=0, strict=True)
    text: str = Field(min_length=1, max_length=4000)
    role: Literal["patient", "clinician", "caregiver", "unknown"] = "unknown"


class ManualTranscript(ReviewAttestation):
    audio_asset_id: UUID
    segments: list[ManualSegment] = Field(min_length=1, max_length=10000)


class ApprovalInput(Strict):
    note_version_id: UUID
    expected_note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_report_id: UUID
    patient_identifiers_reconfirmed: Literal[True]
    attestation_version: Literal["clinician_review_v1"] = "clinician_review_v1"


class ExportInput(Strict):
    approval_id: UUID
    format: Literal["markdown", "text", "json"]


class AmendmentInput(Strict):
    approval_id: UUID
    reason: str = Field(min_length=10, max_length=2000)


class ResolutionInput(Strict):
    expected_note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fact_id: UUID
    action: Literal["clinician_correction"]
    corrected_text: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=20, max_length=2000)
