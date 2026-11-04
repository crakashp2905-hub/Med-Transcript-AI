"""Typed persistence boundaries with migration-compatible, lossless validation."""
from copy import deepcopy
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from services.review.models import Fact, Evidence
from services.review.relationships import ClinicalRelationship

EvidenceSpan = Evidence
ClaimRelation = ClinicalRelationship


class StableRecord(BaseModel):
    model_config = ConfigDict(extra='allow')
    schema_version: Literal['1.0'] = '1.0'


class ClinicalFact(Fact):
    model_config = ConfigDict(extra='allow')
    review_actor: UUID | None = None
    reviewed_at: datetime | None = None


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra='allow')
    segment_id: UUID
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(max_length=4000)
    role: Literal['patient', 'clinician', 'caregiver', 'interpreter', 'other', 'unknown']
    channel_index: int | None = Field(default=None, ge=0, le=7)

    @model_validator(mode='after')
    def positive_interval(self):
        if self.end_ms <= self.start_ms:
            raise ValueError('invalid_segment_interval')
        return self


class TranscriptVersion(StableRecord):
    id: UUID
    encounter_id: UUID
    audio_asset_id: UUID
    version: int = Field(gt=0)
    duration_ms: float = Field(gt=0, le=3600000)
    segments: list[TranscriptSegment] = Field(max_length=10000)


class NoteVersion(StableRecord):
    id: UUID
    encounter_id: UUID
    version: int = Field(gt=0)
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    verification_report_id: UUID
    facts: list[ClinicalFact] = Field(min_length=1, max_length=300)
    sections: list[dict] = Field(max_length=4)


class VerificationFinding(BaseModel):
    model_config = ConfigDict(extra='allow')
    finding_id: UUID
    code: str = Field(pattern=r'^[a-z0-9_]+$')
    message: str = Field(max_length=2000)
    severity: Literal['critical', 'major', 'minor', 'info', 'warning']
    fact_id: UUID | None = None
    blocks_approval: bool = True


class VerificationReport(StableRecord):
    id: UUID
    note_version_id: UUID
    note_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    findings: list[VerificationFinding] = Field(max_length=10000)
    gate: Literal['ready', 'blocked']

    @model_validator(mode='after')
    def consistent_gate(self):
        if (self.gate == 'ready') != (len(self.findings) == 0):
            raise ValueError('verification_gate_inconsistent')
        return self


class Approval(StableRecord):
    id: UUID
    note_version_id: UUID
    note_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    transcript_version_id: UUID
    transcript_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    verification_report_id: UUID
    clinician_id: UUID
    approved_at: datetime
    attestation_version: Literal['clinician_review_v1']
    patient_identifiers_reconfirmed: Literal[True]


class InferenceReceipt(StableRecord):
    status: str
    model_digest: str | None = None
    config_sha256: str | None = None
    limitations: list[str] = Field(default_factory=list)
    independent_clinical_gold: Literal[False] = False


class ModelProposal(StableRecord):
    id: UUID
    transcript_version_id: UUID | None = None
    transcript_sha256: str | None = None


class AuditRecord(StableRecord):
    id: UUID
    tenant: UUID
    actor: UUID | Literal['local_ingest_worker', 'local_asr_worker']
    action: str = Field(pattern=r'^[a-z0-9_]+$')
    resource: str = Field(max_length=200)
    time: datetime


MODELS = {'transcript': TranscriptVersion, 'note': NoteVersion, 'verification': VerificationReport,
          'approval': Approval, 'proposal': ModelProposal, 'audit': AuditRecord}


def migrate_legacy(kind, body):
    if kind not in MODELS:
        raise ValueError('unsupported_record_kind')
    version = body.get('schema_version', 'legacy-0')
    if version not in ('legacy-0', '1.0'):
        raise ValueError('unsupported_schema_version')
    result = deepcopy(body)
    result['schema_version'] = '1.0'
    return result


def validate_record(kind, body):
    # Validate a migrated copy; immutable original serialization and hashes stay
    # unchanged. A persisted migration requires an explicit new immutable version.
    return MODELS[kind].model_validate(migrate_legacy(kind, body))
