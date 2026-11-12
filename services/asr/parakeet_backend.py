"""Local-only Parakeet ONNX candidate backend; no downloads or made-up timing."""

import importlib.metadata
import re
from pathlib import Path

from services.asr.backend import BackendError
from services.audio_provenance import file_sha256


class ParakeetOnnxBackend:
    def __init__(self, model_dir, revision, expected_artifacts, license_id):
        self.model_dir = Path(model_dir)
        self.revision = revision
        self.expected_artifacts = dict(expected_artifacts)
        self.license_id = license_id
        self._recognizer = None

    def availability(self):
        root = self.model_dir
        if (
            not root.is_absolute()
            or root.is_symlink()
            or not root.is_dir()
            or not self.expected_artifacts
            or any(
                not isinstance(name, str)
                or not name
                or not isinstance(digest, str)
                or Path(name).is_absolute()
                or ".." in Path(name).parts
                or not re.fullmatch(r"[a-f0-9]{64}", digest)
                for name, digest in self.expected_artifacts.items()
            )
        ):
            return {
                "status": "unavailable",
                "reason_code": "model_unavailable",
                "automatic_download": False,
            }
        try:
            actual_files = {
                item.relative_to(root).as_posix()
                for item in root.rglob("*")
                if item.is_file() or item.is_symlink()
            }
            if actual_files != set(self.expected_artifacts):
                raise ValueError
            for name, digest in self.expected_artifacts.items():
                path = root / name
                if (
                    any(
                        parent.is_symlink()
                        for parent in (path, *path.parents)
                        if parent != root.parent
                    )
                    or not path.is_file()
                    or file_sha256(path) != digest
                ):
                    raise ValueError
        except (OSError, ValueError):
            return {
                "status": "integrity_failed",
                "reason_code": "model_integrity_failure",
                "automatic_download": False,
            }
        try:
            if importlib.metadata.version("onnx-asr") != "0.12.0":
                return {
                    "status": "unavailable",
                    "reason_code": "asr_runtime_mismatch",
                    "automatic_download": False,
                }
            importlib.metadata.version("onnxruntime")
        except importlib.metadata.PackageNotFoundError:
            return {
                "status": "unavailable",
                "reason_code": "asr_dependency_missing",
                "automatic_download": False,
            }
        return {
            "status": "available_not_admitted",
            "reason_code": None,
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
            "backend_id": "parakeet-tdt-0.6b-v2",
            "runtime_version": "onnx-asr-0.12.0",
            "model_revision": self.revision,
            "artifact_sha256": dict(self.expected_artifacts),
            "license_id": self.license_id,
            "device": "cpu",
            "automatic_download": False,
        }

    def _load(self):
        import onnx_asr
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        return onnx_asr.load_model(
            "nemo-parakeet-tdt-0.6b-v2",
            path=str(self.model_dir),
            quantization="int8",
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def transcribe(self, source, metadata, checkpoint):
        if metadata.get("channels") != 1 or metadata.get("sample_rate") != 16000:
            raise BackendError("backend_input_unsupported")
        if self.availability()["status"] != "available_not_admitted":
            raise BackendError("backend_unavailable")
        checkpoint()
        if self._recognizer is None:
            self._recognizer = self._load()
        text = self._recognizer.recognize(str(source))
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
        recognizer, self._recognizer = self._recognizer, None
        close = getattr(recognizer, "close", None)
        if callable(close):
            close()
