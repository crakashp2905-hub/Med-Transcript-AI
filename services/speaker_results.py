"""Independent speaker clustering, role, and channel result boundaries."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeakerClusteringResult:
    segments: tuple
    confidence: str = "unconfirmed"


@dataclass(frozen=True)
class RoleIdentificationResult:
    assignments: tuple
    status: str = "clinician_confirmation_required"


@dataclass(frozen=True)
class ChannelAssignmentResult:
    channels: tuple
    status: str = "unconfirmed"
