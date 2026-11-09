"""Deterministic, model-free adapters for offline smoke paths.

These adapters are synthetic transport fixtures. They never claim ASR quality,
speaker accuracy, clinical extraction quality, or verifier validity.
"""
from dataclasses import dataclass


class SyntheticOnlyError(ValueError):
    pass


def _require_synthetic(synthetic):
    if synthetic is not True:
        raise SyntheticOnlyError("synthetic_adapter_requires_explicit_synthetic_scope")


@dataclass(frozen=True)
class FakeASRAdapter:
    """Return predeclared transcript segments without reading audio or weights."""
    segments: tuple[dict, ...]

    def transcribe(self, source, metadata, checkpoint=lambda: None, *, synthetic=False):
        _require_synthetic(synthetic)
        checkpoint()
        return {"segments": [dict(row) for row in self.segments],
                "duration_seconds": metadata.get("frames", 0) / 16000,
                "inference_executed": False, "provider_mode": "synthetic_fixture",
                "quality_status": "not_an_asr_measurement"}


@dataclass(frozen=True)
class FakeDiarizationAdapter:
    turns: tuple[dict, ...]

    def diarize(self, *, synthetic=False):
        _require_synthetic(synthetic)
        return {"segments": [dict(row) for row in self.turns],
                "role_assignment": "clinician_confirmation_required",
                "quality_status": "not_a_diarization_measurement"}


class FakeExtractionAdapter:
    def extract(self, transcript, *, synthetic=False):
        _require_synthetic(synthetic)
        return {"facts": [], "source_transcript_id": transcript.get("id"),
                "quality_status": "not_a_clinical_extraction_measurement"}


class FakeVerifierAdapter:
    def verify(self, claims, *, synthetic=False):
        _require_synthetic(synthetic)
        return {"findings": [], "claims_checked": len(claims),
                "approval_clearance": "never", "quality_status": "not_a_clinical_verification_measurement"}
