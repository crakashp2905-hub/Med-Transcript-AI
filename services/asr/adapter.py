"""faster-whisper baseline: local artifacts, PCM input, full lazy-result consumption."""

import importlib.metadata
import math
import wave
from pathlib import Path

from services.asr.profiles import ASRProfile


class ASRFailure(Exception):
    SAFE_CODES = {"asr_dependency_missing", "asr_runtime_mismatch", "model_integrity_failure",
                  "unsupported_asr_input", "invalid_asr_output", "asset_integrity_failure",
                  "asset_unavailable", "authorization_required", "worker_lease_lost", "asr_failed"}

    def __init__(self, code):
        self.code = code if code in self.SAFE_CODES else "asr_failed"
        super().__init__(self.code)


class FasterWhisperAdapter:
    def __init__(self, profile: ASRProfile):
        self.profile = profile

    def transcribe(self, source: Path, metadata: dict, checkpoint):
        if metadata["channels"] != 1 or metadata["sample_rate"] != 16000:
            raise ASRFailure("unsupported_asr_input")
        try:
            self.profile.verify_artifacts()
        except (ValueError, OSError):
            raise ASRFailure("model_integrity_failure") from None
        try:
            runtime_packages = {name: importlib.metadata.version(name) for name in
                                ("faster-whisper", "ctranslate2", "tokenizers", "numpy", "av", "onnxruntime")}
            if runtime_packages["faster-whisper"] != self.profile.runtime_version:
                raise ASRFailure("asr_runtime_mismatch")
            import numpy as np
            from faster_whisper import WhisperModel
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
            return {"segments": [], "duration_seconds": metadata["frames"] / 16000,
                    "digital_silence": True, "inference_executed": False, "runtime_packages": runtime_packages}
        checkpoint()
        model = WhisperModel(self.profile.model_dir, device=self.profile.device,
                             compute_type=self.profile.compute_type, cpu_threads=self.profile.cpu_threads,
                             num_workers=1, local_files_only=True)
        segments, info = model.transcribe(normalized, language="en", task="transcribe",
            beam_size=self.profile.beam_size, temperature=0.0, vad_filter=False,
            word_timestamps=False, condition_on_previous_text=False, log_progress=False)
        raw, total_chars = [], 0
        # Iteration performs inference: never publish a partially consumed generator.
        for segment in segments:
            checkpoint()
            if len(raw) >= 10000 or not isinstance(segment.text, str):
                raise ASRFailure("invalid_asr_output")
            total_chars += len(segment.text)
            if total_chars > 500_000 or len(segment.text) > 4000:
                raise ASRFailure("invalid_asr_output")
            raw.append({"start_seconds": segment.start, "end_seconds": segment.end, "text": segment.text})
        checkpoint()
        duration = info.duration
        if not isinstance(duration, (float, int)) or not math.isfinite(duration):
            raise ASRFailure("invalid_asr_output")
        return {"segments": raw, "duration_seconds": duration, "digital_silence": False,
                "inference_executed": True, "runtime_packages": runtime_packages}
