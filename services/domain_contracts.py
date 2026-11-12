"""Typed persistence boundaries with migration-compatible, lossless validation."""

from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
    ValidationError,
    StrictInt,
)
from services.review.models import Fact, Evidence
from services.review.relationships import ClinicalRelationship

EvidenceSpan = Evidence
ClaimRelation = ClinicalRelationship


class StableRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: Literal["1.0"] = "1.0"


class AudioSource(StableRecord):
    id: UUID
    encounter_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_count: int = Field(gt=0, strict=True)
    media_type: Literal[
        "audio/wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg"
    ]
    state: Literal["sealed", "normalized"]
    duration_ms: float | None = Field(default=None, gt=0, le=3600000)
    channel_count: int | None = Field(default=None, ge=1, le=8, strict=True)


class ProcessingConsent(StableRecord):
    id: UUID
    encounter_id: UUID
    scopes: list[Literal["recording", "local_processing", "hosted_text_processing"]] = (
        Field(min_length=1, max_length=3)
    )
    policy_version: str = Field(min_length=1, max_length=80)
    method: Literal["written", "verbal_documented"]
    granted_at: datetime
    expires_at: datetime
    withdrawn_at: datetime | None = None

    @model_validator(mode="after")
    def consent_lifecycle(self):
        if len(set(self.scopes)) != len(self.scopes):
            raise ValueError("duplicate_processing_consent_scope")
        if self.granted_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("processing_consent_timezone_required")
        if self.expires_at <= self.granted_at:
            raise ValueError("processing_consent_expiry_invalid")
        if self.withdrawn_at is not None and (
            self.withdrawn_at.tzinfo is None or self.withdrawn_at < self.granted_at
        ):
            raise ValueError("processing_consent_withdrawal_invalid")
        return self


class ClinicalFact(Fact):
    model_config = ConfigDict(extra="allow")
    review_actor: UUID | None = None
    reviewed_at: datetime | None = None


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="allow")
    segment_id: UUID
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(max_length=4000)
    role: Literal[
        "patient", "clinician", "caregiver", "interpreter", "other", "unknown"
    ]
    channel_index: int | None = Field(default=None, ge=0, le=7)

    @model_validator(mode="after")
    def positive_interval(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("invalid_segment_interval")
        return self


class TranscriptVersion(StableRecord):
    id: UUID
    encounter_id: UUID
    audio_asset_id: UUID
    version: int = Field(gt=0)
    duration_ms: float = Field(gt=0, le=3600000)
    segments: list[TranscriptSegment] = Field(max_length=10000)


class NoteStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    statement_id: UUID
    text: str = Field(min_length=1, max_length=4000)
    fact_ids: list[UUID] = Field(min_length=1, max_length=20)
    origin: Literal["source_linked", "clinician_entered"]
    source_version_id: UUID | None = None
    evidence: EvidenceSpan | None = None


class NoteSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Literal["subjective", "objective", "assessment", "plan"]
    statements: list[NoteStatement] = Field(max_length=300)


class NoteVersion(StableRecord):
    id: UUID
    encounter_id: UUID
    version: int = Field(gt=0)
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_report_id: UUID
    facts: list[ClinicalFact] = Field(min_length=1, max_length=300)
    sections: list[NoteSection] = Field(max_length=4)

    @model_validator(mode="after")
    def unique_note_sections(self):
        keys = [section.key for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_note_section")
        return self


class VerificationFinding(BaseModel):
    model_config = ConfigDict(extra="allow")
    finding_id: UUID
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    message: str = Field(max_length=2000)
    severity: Literal["critical", "major", "minor", "info", "warning"]
    fact_id: UUID | None = None
    blocks_approval: bool = True


class VerificationReport(StableRecord):
    id: UUID
    note_version_id: UUID
    note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    findings: list[VerificationFinding] = Field(max_length=10000)
    gate: Literal["ready", "blocked"]

    @model_validator(mode="after")
    def consistent_gate(self):
        if (self.gate == "ready") != (len(self.findings) == 0):
            raise ValueError("verification_gate_inconsistent")
        return self


class Approval(StableRecord):
    id: UUID
    note_version_id: UUID
    note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verification_report_id: UUID
    clinician_id: UUID
    approved_at: datetime
    attestation_version: Literal["clinician_review_v1"]
    patient_identifiers_reconfirmed: Literal[True]


class ExportRecord(StableRecord):
    id: UUID
    encounter_id: UUID
    approval_id: UUID
    note_version_id: UUID
    note_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    format: Literal["markdown", "text", "json", "fhir"]
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime


class InferenceReceipt(StableRecord):
    status: Literal[
        "completed", "failed", "not_configured", "skipped", "timeout", "abstained"
    ]
    model_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    config_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    duration_ms: float | None = Field(default=None, ge=0)
    limitations: list[str] = Field(default_factory=list)
    independent_clinical_gold: Literal[False] = False


class ModelProposal(StableRecord):
    id: UUID
    transcript_version_id: UUID | None = None
    transcript_sha256: str | None = None


class BoundProposal(ModelProposal):
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["unreviewed_proposal_not_approvable"]


class ProposedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: Literal["subjective", "objective", "assessment", "plan"]
    text: str = Field(min_length=1, max_length=4000)
    fact_ids: list[UUID] = Field(min_length=1, max_length=20)


class ProposedDraft(BaseModel):
    model_config = ConfigDict(extra="allow")
    statements: list[ProposedStatement] = Field(max_length=300)


class DraftProposal(BoundProposal):
    source_facts: list[ClinicalFact] = Field(min_length=1, max_length=300)
    draft: ProposedDraft

    @model_validator(mode="after")
    def known_reviewed_facts(self):
        eligible = {
            f.fact_id for f in self.source_facts if f.reviewed and not f.excluded
        }
        if any(
            fid not in eligible for s in self.draft.statements for fid in s.fact_ids
        ):
            raise ValueError("proposal_cites_unknown_or_unreviewed_fact")
        return self


class FactProposal(BoundProposal):
    facts: list[ClinicalFact] = Field(max_length=300)

    @model_validator(mode="after")
    def proposals_stay_unreviewed(self):
        if any(f.reviewed or f.critical_reviewed for f in self.facts):
            raise ValueError("model_proposal_cannot_mark_review_complete")
        return self


class SemanticVerdict(BaseModel):
    model_config = ConfigDict(extra="allow")
    fact_id: UUID
    label: Literal["supported", "contradicted", "unsupported", "ambiguous"]
    evidence_quote: str = Field(max_length=4000)
    reason: str = Field(min_length=1, max_length=500)


class SemanticProposal(BoundProposal):
    note_version_id: UUID
    verdicts: list[SemanticVerdict] = Field(min_length=1, max_length=300)
    checked_fact_ids: list[UUID] = Field(min_length=1, max_length=300)
    unchecked_fact_ids: list[UUID] = Field(max_length=300)
    evidence_linked_fact_count: int = Field(ge=1, le=300, strict=True)
    total_note_fact_count: int | None = Field(default=None, ge=1, le=300, strict=True)
    unverifiable_no_source_fact_ids: list[UUID] = Field(
        default_factory=list, max_length=300
    )
    excluded_fact_ids: list[UUID] = Field(default_factory=list, max_length=300)
    completion_status: (
        Literal["complete_evidence_linked_scope", "partial_selected_scope"] | None
    ) = None
    independent_clinical_calibration: Literal[False]
    cannot_clear_existing_findings: Literal[True]

    @model_validator(mode="after")
    def exact_coverage(self):
        checked = set(self.checked_fact_ids)
        unchecked = set(self.unchecked_fact_ids)
        if (
            len(checked) != len(self.checked_fact_ids)
            or len(unchecked) != len(self.unchecked_fact_ids)
            or checked & unchecked
            or len(checked) + len(unchecked) != self.evidence_linked_fact_count
            or len(self.verdicts) != len(checked)
            or {v.fact_id for v in self.verdicts} != checked
        ):
            raise ValueError("semantic_proposal_coverage_mismatch")
        if self.total_note_fact_count is not None:
            no_source = set(self.unverifiable_no_source_fact_ids)
            excluded = set(self.excluded_fact_ids)
            groups = [checked, unchecked, no_source, excluded]
            if (
                sum(map(len, groups)) != self.total_note_fact_count
                or len(set.union(*groups)) != self.total_note_fact_count
                or len(no_source) != len(self.unverifiable_no_source_fact_ids)
                or len(excluded) != len(self.excluded_fact_ids)
                or self.completion_status
                != (
                    "complete_evidence_linked_scope"
                    if not unchecked
                    else "partial_selected_scope"
                )
            ):
                raise ValueError("semantic_proposal_total_note_coverage_mismatch")
        return self


class ReviewSession(StableRecord):
    id: UUID
    note_version_id: UUID
    actor: UUID
    started_at: datetime
    drafting_arm: Literal["unspecified", "manual", "deterministic", "local_qwen"] = (
        "unspecified"
    )
    arm_attribution: Literal["clinician_selected_not_independently_verified"] = (
        "clinician_selected_not_independently_verified"
    )

    @model_validator(mode="after")
    def aware_start(self):
        if self.started_at.tzinfo is None:
            raise ValueError("review_session_timezone_required")
        return self


class ReviewMetric(StableRecord):
    id: UUID
    session_id: UUID
    before_note: UUID
    after_note: UUID
    word_edits: int = Field(ge=0, strict=True)
    review_wall_ms: int = Field(ge=0, strict=True)
    self_reported_active_ms: int | None = Field(default=None, ge=0, strict=True)
    active_time_verified: Literal[False]
    raw_text_in_telemetry: Literal[False]
    # Earlier metric bodies did not include structured edit counts. Validate a
    # copy without injecting invented zero observations into the stored payload.
    facts_added: int | None = Field(default=None, ge=0, strict=True)
    facts_removed: int | None = Field(default=None, ge=0, strict=True)
    field_edit_counts: dict[str, StrictInt] = Field(default_factory=dict)
    drafting_arm: Literal["unspecified", "manual", "deterministic", "local_qwen"] = (
        "unspecified"
    )

    @model_validator(mode="after")
    def bounded_observations(self):
        if (
            self.self_reported_active_ms is not None
            and self.self_reported_active_ms > self.review_wall_ms
        ):
            raise ValueError("active_time_exceeds_observed_wall_time")
        if any(type(v) is not int or v < 0 for v in self.field_edit_counts.values()):
            raise ValueError("invalid_field_edit_counter")
        return self


class AuditRecord(StableRecord):
    id: UUID
    tenant: UUID
    actor: UUID | Literal["local_ingest_worker", "local_asr_worker"]
    action: str = Field(pattern=r"^[a-z0-9_]+$")
    resource: str = Field(max_length=200)
    time: datetime


MODELS = {
    "audio_source": AudioSource,
    "processing_consent": ProcessingConsent,
    "evidence": EvidenceSpan,
    "fact": ClinicalFact,
    "relationship": ClaimRelation,
    "transcript": TranscriptVersion,
    "note": NoteVersion,
    "verification": VerificationReport,
    "approval": Approval,
    "export": ExportRecord,
    "inference_receipt": InferenceReceipt,
    "proposal": ModelProposal,
    "audit": AuditRecord,
    "draft_proposal": DraftProposal,
    "fact_proposal": FactProposal,
    "semantic_check": SemanticProposal,
    "review_session": ReviewSession,
    "review_metric": ReviewMetric,
}


def migrate_legacy(kind, body):
    if kind not in MODELS:
        raise ValueError("unsupported_record_kind")
    if not isinstance(body, dict):
        raise ValueError("persisted_record_object_required")
    version = body.get("schema_version", "legacy-0")
    if version not in ("legacy-0", "1.0"):
        raise ValueError("unsupported_schema_version")
    result = deepcopy(body)
    result["schema_version"] = "1.0"
    return result


def validate_record(kind, body):
    # Validate a migrated copy; immutable original serialization and hashes stay
    # unchanged. A persisted migration requires an explicit new immutable version.
    try:
        migrated = migrate_legacy(kind, body)
        return MODELS[kind].model_validate(migrated)
    except ValidationError:
        # Pydantic's default exception includes input values. Persisted clinical
        # content must not escape through logs or API error details.
        raise ValueError("invalid_persisted_record_schema") from None
