"""faster-whisper baseline: local artifacts, PCM input, full lazy-result consumption."""

import importlib.metadata
import math
import os
import platform
import time
from functools import lru_cache
import wave
from pathlib import Path

from services.asr.profiles import ASRProfile
from services.asr.timestamps import capability as timestamp_capability_info


class ASRFailure(Exception):
    SAFE_CODES = {
        "asr_dependency_missing",
        "asr_runtime_mismatch",
        "model_integrity_failure",
        "model_unavailable",
        "unsupported_asr_input",
        "invalid_asr_output",
        "asset_integrity_failure",
        "asset_unavailable",
        "authorization_required",
        "worker_lease_lost",
        "asr_failed",
        "resource_capacity_exceeded",
    }

    def __init__(self, code):
        self.code = code if code in self.SAFE_CODES else "asr_failed"
        super().__init__(self.code)


@lru_cache(maxsize=1)
def loaded_model(profile_json):
    """One pinned local model per worker process; never cache recognized text."""
    from faster_whisper import WhisperModel

    profile = ASRProfile.model_validate_json(profile_json)
    return WhisperModel(
        profile.model_dir,
        device=profile.device,
        compute_type=profile.compute_type,
        cpu_threads=profile.cpu_threads,
        num_workers=1,
        local_files_only=True,
    )


class FasterWhisperAdapter:
    def __init__(self, profile: ASRProfile):
        self.profile = profile

    def availability(self):
        return self.profile.availability()

    def timestamp_capability(self):
        declared = timestamp_capability_info("whisper", has_native_segments=True)
        return {
            "kind": declared.kind,
            "native": declared.native,
            "word_alignment_validated": declared.word_alignment_validated,
        }

    def n_best_capability(self):
        return {"supported": False, "kind": "none"}

    def confidence_capability(self):
        return {"supported": False, "kind": "none", "calibrated": False}

    def runtime_receipt(self):
        return {
            "backend_id": "faster-whisper",
            "runtime_version": self.profile.runtime_version,
            "model_revision": self.profile.revision,
            "profile_sha256": self.profile.sha256,
            "artifact_sha256": dict(self.profile.artifacts),
            "license_id": self.profile.license_id,
            "device": self.profile.device,
            "automatic_download": False,
        }

    def _runtime_environment(self):
        return {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "device": self.profile.device,
            "compute_type": self.profile.compute_type,
        }

    def transcribe(self, source: Path, metadata: dict, checkpoint):
        if metadata["channels"] != 1 or metadata["sample_rate"] != 16000:
            raise ASRFailure("unsupported_asr_input")
        availability = self.profile.availability()
        if availability["status"] != "available_not_admitted":
            raise ASRFailure(availability["reason_code"])
        try:
            runtime_packages = {
                name: importlib.metadata.version(name)
                for name in (
                    "faster-whisper",
                    "ctranslate2",
                    "tokenizers",
                    "numpy",
                )
            }
            if runtime_packages["faster-whisper"] != self.profile.runtime_version:
                raise ASRFailure("asr_runtime_mismatch")
            import numpy as np
        except (ImportError, importlib.metadata.PackageNotFoundError):
            raise ASRFailure("asr_dependency_missing") from None

        checkpoint()
        # Bypass PyAV/general media decoding: validated PCM samples enter the engine.
        with wave.open(str(source), "rb") as audio:
            samples = np.frombuffer(audio.readframes(metadata["frames"]), dtype="<i2")
        if len(samples) != metadata["frames"]:
            raise ASRFailure("asset_integrity_failure")
        normalized = samples.astype(np.float32) / 32768.0
        if not np.any(samples):
            return {
                "segments": [],
                "duration_seconds": metadata["frames"] / 16000,
                "digital_silence": True,
                "inference_executed": False,
                "runtime_packages": runtime_packages,
            }
        checkpoint()
        hits = loaded_model.cache_info().hits
        load_started = time.perf_counter()
        model = loaded_model(self.profile.model_dump_json())
        cache_hit = loaded_model.cache_info().hits > hits
        timing = {
            "trace_schema": "asr_model_init_v1",
            "initialization_state": "warm" if cache_hit else "cold",
            "model_cache_hit": cache_hit,
            "model_load_seconds": time.perf_counter() - load_started,
            "model_profile_sha256": self.profile.sha256,
            "model_revision": self.profile.revision,
            "artifact_sha256": dict(self.profile.artifacts),
            "runtime_environment": self._runtime_environment(),
        }
        inference_started = time.perf_counter()
        decode_options = {
            "language": "en",
            "task": "transcribe",
            "beam_size": self.profile.beam_size,
            "temperature": 0.0,
            "vad_filter": False,
            "word_timestamps": False,
            "condition_on_previous_text": False,
            "log_progress": False,
        }
        context_bias = None
        if "clinical_bias_terms" in metadata:
            from services.asr.context_biasing import build_context_bias

            context_bias = build_context_bias(metadata["clinical_bias_terms"])
            decode_options["hotwords"] = context_bias["hotwords"]
        segments, info = model.transcribe(
            normalized,
            **decode_options,
        )
        raw: list[dict[str, object]] = []
        total_chars = 0
        # Iteration performs inference: never publish a partially consumed generator.
        for segment in segments:
            checkpoint()
            if len(raw) >= 10000 or not isinstance(segment.text, str):
                raise ASRFailure("invalid_asr_output")
            total_chars += len(segment.text)
            if total_chars > 500_000 or len(segment.text) > 4000:
                raise ASRFailure("invalid_asr_output")
            row = {
                "start_seconds": segment.start,
                "end_seconds": segment.end,
                "text": segment.text,
            }
            # faster-whisper exposes the winning sequence's token IDs and
            # average decoder log probability, but not an N-best list or
            # calibrated confidence. Preserve only the native evidence it
            # actually returns; never derive confidence from missing values.
            token_ids = getattr(segment, "tokens", None)
            average_logprob = getattr(segment, "avg_logprob", None)
            if token_ids is not None or average_logprob is not None:
                if (
                    not isinstance(token_ids, list)
                    or len(token_ids) > 20000
                    or any(type(token) is not int or token < 0 for token in token_ids)
                    or isinstance(average_logprob, bool)
                    or not isinstance(average_logprob, (int, float))
                    or not math.isfinite(average_logprob)
                    or average_logprob > 0
                    or average_logprob < -100
                ):
                    raise ASRFailure("invalid_asr_output")
                row["decoder_evidence"] = {
                    "kind": "faster_whisper_best_sequence_v1",
                    "token_ids": token_ids,
                    "average_logprob": average_logprob,
                    "n_best_supported": False,
                    "calibrated": False,
                }
            raw.append(row)
        checkpoint()
        duration = info.duration
        if not isinstance(duration, (float, int)) or not math.isfinite(duration):
            raise ASRFailure("invalid_asr_output")
        timing["inference_seconds"] = time.perf_counter() - inference_started
        return {
            "segments": raw,
            "duration_seconds": duration,
            "digital_silence": False,
            "timing": timing,
            "inference_executed": True,
            "runtime_packages": runtime_packages,
            "context_biasing": context_bias
            or {"status": "not_requested", "text_mutation": False},
        }
