"""Deterministic, model-free adapters for offline smoke paths.

These adapters are synthetic transport fixtures. They never claim ASR quality,
speaker accuracy, clinical extraction quality, or verifier validity.
"""

from dataclasses import dataclass
from services.provider_interfaces import (
    ASRProvider,
    DiarizationProvider,
    ExtractionProvider,
    VerificationProvider,
)


class SyntheticOnlyError(ValueError):
    pass


def _require_synthetic(synthetic):
    if synthetic is not True:
        raise SyntheticOnlyError("synthetic_adapter_requires_explicit_synthetic_scope")


@dataclass(frozen=True)
class FakeASRAdapter(ASRProvider):
    """Return predeclared transcript segments without reading audio or weights."""

    segments: tuple[dict, ...]

    def availability(self):
        return {"status": "available_not_admitted", "provider_mode": "fixture"}

    def timestamp_capability(self):
        return {"kind": "segment", "native": True}

    def n_best_capability(self):
        return {"supported": False}

    def confidence_capability(self):
        return {"supported": False, "calibrated": False}

    def runtime_receipt(self):
        return {
            "backend_id": "synthetic_fixture",
            "runtime_version": "none",
            "model_revision": "none",
        }

    def transcribe(self, source, metadata, checkpoint=lambda: None, *, synthetic=False):
        _require_synthetic(synthetic)
        checkpoint()
        return {
            "segments": [dict(row) for row in self.segments],
            "duration_seconds": metadata.get("frames", 0) / 16000,
            "inference_executed": False,
            "provider_mode": "synthetic_fixture",
            "quality_status": "not_an_asr_measurement",
        }


@dataclass(frozen=True)
class FakeDiarizationAdapter(DiarizationProvider):
    turns: tuple[dict, ...]

    def diarize(self, audio, manifest, checkpoint=lambda: None, *, synthetic=False):
        _require_synthetic(synthetic)
        checkpoint()
        return {
            "segments": [dict(row) for row in self.turns],
            "role_assignment": "clinician_confirmation_required",
            "quality_status": "not_a_diarization_measurement",
        }


class FakeExtractionAdapter(ExtractionProvider):
    def extract_facts(self, transcript, *, authorized, synthetic):
        _require_synthetic(synthetic)
        if not authorized:
            raise SyntheticOnlyError("explicit_authorization_required")
        return {
            "facts": [],
            "source_transcript_id": transcript.get("id"),
            "quality_status": "not_a_clinical_extraction_measurement",
        }


class FakeVerifierAdapter(VerificationProvider):
    def check_claims(self, claims, *, authorized, synthetic):
        _require_synthetic(synthetic)
        if not authorized:
            raise SyntheticOnlyError("explicit_authorization_required")
        return {
            "findings": [],
            "claims_checked": len(claims),
            "approval_clearance": "never",
            "quality_status": "not_a_clinical_verification_measurement",
        }
