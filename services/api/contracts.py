"""Stable typed request/identity contracts; re-exported from api.main for compatibility."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field, field_validator
from services.api.ingest import MAX_UPLOAD_BYTES

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_.-]+$",
    ),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(StrictModel):
    tenant_id: UUID
    clinician_id: UUID
    role: Literal["clinician", "viewer"] = "clinician"


class EncounterInput(StrictModel):
    patient_reference_id: UUID
    patient_identifiers_confirmed: Literal[True]
    language: Literal["en"] = "en"
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    workflow: Literal["outpatient_general_medicine"] = "outpatient_general_medicine"
    requested_inference_mode: Literal["fully_local", "hybrid_text"] = "fully_local"
    synthetic_data: Literal[True]

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value


class AuthorizationInput(StrictModel):
    scopes: list[Literal["recording", "local_processing", "hosted_text_processing"]] = (
        Field(min_length=1, max_length=3)
    )
    policy_version: str = Field(
        min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    method: Literal["written", "verbal_documented"]
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value):
        if value.tzinfo is None or value <= datetime.now(timezone.utc):
            raise ValueError("Expiry must be timezone-aware and in the future")
        return value


class UploadInput(StrictModel):
    bytes: int = Field(gt=0, le=MAX_UPLOAD_BYTES, strict=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: Literal[
        "audio/wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg"
    ] = "audio/wav"


class TranscriptionInput(StrictModel):
    audio_asset_id: UUID
    inference_profile_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    preview_only: bool = False
    preview_session_id: UUID | None = None
    timeline_offset_ms: int = Field(default=0, ge=0, le=3600000, strict=True)
