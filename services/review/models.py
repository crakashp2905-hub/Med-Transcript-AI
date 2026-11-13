from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ClinicalAssertion = Literal["affirmed", "negated", "uncertain", "not_stated"]


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

    @model_validator(mode="after")
    def exact_span_width(self):
        if self.end_char - self.start_char != len(self.quote):
            raise ValueError("evidence_span_length_mismatch")
        return self


class FactRelation(Strict):
    related_fact_id: UUID
    relation_type: Literal[
        "medication",
        "dose",
        "route",
        "frequency",
        "duration",
        "temporality",
        "subject",
        "negation",
        "symptom_site",
        "allergy_reaction",
        "other",
    ]


class Fact(Strict):
    fact_id: UUID
    category: Literal[
        "symptom", "medication", "allergy", "measurement", "assessment", "plan", "other"
    ] = "other"
    section: Literal["subjective", "objective", "assessment", "plan"] = "subjective"
    text: str = Field(min_length=1, max_length=4000)
    subject: Literal["patient", "family", "caregiver", "other", "unknown"] = "unknown"
    assertion: ClinicalAssertion = "uncertain"
    uncertainty: Literal[
        "certain", "possible", "questioned", "ambiguous", "unknown"
    ] = "unknown"
    temporality: Literal["current", "historical", "planned", "unknown"] = "unknown"
    action: Literal[
        "none",
        "start",
        "stop",
        "hold",
        "continue",
        "recommend",
        "order",
        "discuss",
        "unknown",
    ] = "unknown"
    origin: Literal["source_linked", "clinician_entered"] = "source_linked"
    evidence: Evidence | None = None
    relations: list[FactRelation] = Field(default_factory=list, max_length=100)
    source_modality: Literal["transcript", "audio", "clinician_entered", "unknown"] = (
        "unknown"
    )
    reviewed: bool = False
    critical_reviewed: bool = False
    review_status: (
        Literal["unreviewed", "reviewed", "critical_reviewed", "excluded"] | None
    ) = None
    clarification: str = Field(default="", max_length=2000)
    excluded: bool = False
    concept: str | None = Field(default=None, max_length=300)
    anatomical_site: str | None = Field(default=None, max_length=200)
    laterality: Literal["left", "right", "bilateral", "unknown"] = "unknown"
    clinical_source: Literal["patient_report", "clinician_statement", "unknown"] = (
        "unknown"
    )
    extraction_version: str = Field(default="manual_or_legacy", max_length=100)
    medication_name: str | None = Field(default=None, max_length=200)
    dose_value: str | None = Field(default=None, max_length=100)
    dose_unit: str | None = Field(default=None, max_length=50)
    route: str | None = Field(default=None, max_length=100)
    frequency: str | None = Field(default=None, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    allergen: str | None = Field(default=None, max_length=200)
    allergy_reaction: str | None = Field(default=None, max_length=300)
    allergy_severity: Literal["mild", "moderate", "severe", "unknown"] = "unknown"

    @model_validator(mode="after")
    def provenance(self):
        if self.origin == "source_linked" and self.evidence is None:
            raise ValueError("Source-linked facts require evidence")
        if self.origin == "clinician_entered" and (
            self.evidence is not None or len(self.clarification.strip()) < 10
        ):
            raise ValueError(
                "Clinician additions require a reason and cannot invent source evidence"
            )
        self.text.encode("utf-8")
        if self.source_modality == "unknown":
            self.source_modality = (
                "clinician_entered"
                if self.origin == "clinician_entered"
                else "transcript"
            )
        expected_review_status = (
            "excluded"
            if self.excluded
            else "critical_reviewed"
            if self.critical_reviewed
            else "reviewed"
            if self.reviewed
            else "unreviewed"
        )
        if self.review_status is None:
            self.review_status = expected_review_status
        elif self.review_status != expected_review_status:
            raise ValueError("review_status_must_match_review_flags")
        return self


class DraftInput(Strict):
    transcript_version_id: UUID
    facts: list[Fact] = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_fact_relations(self):
        fact_ids = [fact.fact_id for fact in self.facts]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("duplicate_fact_id")
        known_ids = set(fact_ids)
        for fact in self.facts:
            relation_keys = [
                (relation.related_fact_id, relation.relation_type)
                for relation in fact.relations
            ]
            if len(set(relation_keys)) != len(relation_keys):
                raise ValueError("duplicate_fact_relation")
            if any(
                relation.related_fact_id == fact.fact_id
                or relation.related_fact_id not in known_ids
                for relation in fact.relations
            ):
                raise ValueError("fact_relation_target_invalid")
        return self


class DraftProposalInput(DraftInput):
    hosted_text_disclosure_accepted: bool = False


class NoteEdit(DraftInput):
    amendment_reason: str = Field(default="", max_length=2000)


class SegmentEdit(Strict):
    segment_id: UUID | None = None
    parent_segment_ids: list[UUID] = Field(default_factory=list, max_length=10000)
    start_ms: int | None = Field(default=None, ge=0, strict=True)
    end_ms: int | None = Field(default=None, gt=0, strict=True)
    text: str = Field(max_length=4000)
    channel_index: int | None = Field(default=None, ge=0, le=7, strict=True)
    role: Literal[
        "patient", "clinician", "caregiver", "interpreter", "other", "unknown"
    ] = "unknown"


class SpeakerRoleConfirmation(Strict):
    clinician_confirmed: Literal[True]
    assignments: dict[
        str,
        Literal["patient", "clinician", "caregiver", "interpreter", "other", "unknown"],
    ] = Field(min_length=1, max_length=100)


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
    role: Literal[
        "patient", "clinician", "caregiver", "interpreter", "other", "unknown"
    ] = "unknown"


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
    format: Literal["markdown", "text", "json", "fhir"]


class AmendmentInput(Strict):
    approval_id: UUID
    reason: str = Field(min_length=10, max_length=2000)


class ResolutionInput(Strict):
    expected_note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fact_id: UUID
    action: Literal["clinician_correction"]
    corrected_text: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=20, max_length=2000)
