"""Local-only Omi candidate backend with text-only capability declarations."""

import importlib.metadata
from pathlib import Path

from services.asr.backend import BackendError
from services.audio_provenance import file_sha256


class OmiBackend:
    def __init__(
        self,
        model_dir,
        revision,
        model_filename,
        model_sha256,
        license_id,
    ):
        self.model_dir = Path(model_dir)
        self.revision = revision
        self.model_filename = model_filename
        self.model_sha256 = model_sha256
        self.license_id = license_id
        self._predictor = None

    def availability(self):
        root = self.model_dir
        if (
            not root.is_absolute()
            or root.is_symlink()
            or not root.is_dir()
            or not self.model_filename
            or Path(self.model_filename).name != self.model_filename
        ):
            return {
                "status": "unavailable",
                "reason_code": "model_unavailable",
                "automatic_download": False,
            }
        artifact = root / self.model_filename
        if not artifact.is_file() or file_sha256(artifact) != self.model_sha256:
            return {
                "status": "unavailable",
                "reason_code": "model_unavailable",
                "automatic_download": False,
            }
        try:
            if importlib.metadata.version("omi-med-stt") != "0.2.1":
                return {
                    "status": "unavailable",
                    "reason_code": "asr_runtime_mismatch",
                    "automatic_download": False,
                }
            from omi_stt import cpp_runtime

            if self.model_filename != cpp_runtime.DEFAULT_GGUF_FILE:
                return {
                    "status": "integrity_failed",
                    "reason_code": "model_integrity_failure",
                    "automatic_download": False,
                }
            runtime_available = cpp_runtime._cached_parakeet_lib().is_file()
        except (ImportError, importlib.metadata.PackageNotFoundError, OSError):
            runtime_available = False
        return {
            "status": "available_not_admitted" if runtime_available else "unavailable",
            "reason_code": None if runtime_available else "asr_dependency_missing",
            "automatic_download": False,
        }

    def timestamp_capability(self):
        return {"kind": "none", "native": False}

    def n_best_capability(self):
        return {"supported": False, "kind": "none"}

    def confidence_capability(self):
        return {"supported": False, "kind": "none", "calibrated": False}

    def runtime_receipt(self):
        return {
            "backend_id": "omi-med-stt",
            "runtime_version": "0.2.1",
            "model_revision": self.revision,
            "artifact_sha256": {self.model_filename: self.model_sha256},
            "license_id": self.license_id,
            "device": "cpu",
            "automatic_download": False,
        }

    def transcribe(self, source, metadata, checkpoint):
        if metadata.get("channels") != 1 or metadata.get("sample_rate") != 16000:
            raise BackendError("backend_input_unsupported")
        if self.availability()["status"] != "available_not_admitted":
            raise BackendError("backend_unavailable")
        checkpoint()
        if self._predictor is None:
            from services.omi_adapter import OmiPredictor

            self._predictor = OmiPredictor(
                self.model_dir,
                self.revision,
                allow_empty_output=False,
            )
        text = self._predictor(source)
        checkpoint()
        if not isinstance(text, str) or not text.strip():
            raise BackendError("backend_output_invalid")
        return {
            "text": text,
            "segments": None,
            "timestamp_kind": "none",
            "confidence": None,
            "inference_executed": True,
        }

    def close(self):
        if self._predictor is not None:
            self._predictor.close()
            self._predictor = None
