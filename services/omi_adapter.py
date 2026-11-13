"""Pinned Omi CPU C API lifecycle for text-only benchmarks, with bounded DLL handles."""

import wave
import importlib.metadata
from pathlib import Path

from services.audio_provenance import file_sha256


PINNED_REVISION = "30d74219feead34843fae59e855f740db78ed2bd"
PINNED_GGUF_SHA256 = "c4f364a730df7aa9bb0714cda1b1ad5e3104331db9919bb0e2a379d0fb64dbab"


class OmiPredictor:
    def __init__(self, model_dir, revision, *, allow_empty_output=False):
        if revision != PINNED_REVISION:
            raise ValueError("Omi model revision is not pinned")
        if importlib.metadata.version("omi-med-stt") != "0.2.1":
            raise ValueError("This lifecycle adapter requires pinned omi-med-stt 0.2.1")
        import numpy as np
        from omi_stt import cpp_runtime as runtime

        self.np, self.runtime = np, runtime
        self.allow_empty_output, self.last_empty_output = allow_empty_output, False
        root = Path(model_dir)
        if not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise ValueError("A pinned local Omi model directory is required")
        model = root / runtime.DEFAULT_GGUF_FILE
        if (
            model.is_symlink()
            or not model.is_file()
            or file_sha256(model) != PINNED_GGUF_SHA256
        ):
            raise ValueError(
                "Pinned local Omi model artifact is unavailable or changed"
            )
        library = runtime._find_parakeet_lib(auto_install=False, backend="cpu")
        self.capi = runtime._ParakeetCAPI(
            library, str(model.resolve()), decoder="tdt", backend="cpu", threads=4
        )

    def __call__(self, path):
        self.last_empty_output = False
        with wave.open(str(path), "rb") as stream:
            pcm = self.np.frombuffer(
                stream.readframes(stream.getnframes()), dtype="<i2"
            )
        audio = self.np.ascontiguousarray(pcm.astype(self.np.float32) / 32768.0)
        try:
            result = self.capi.transcribe_pcm(audio)
        except RuntimeError as exc:
            # A non-null native result with zero tokens is different from a native
            # inference failure. Opt-in only: historical benchmark behavior stays fixed.
            if (
                self.allow_empty_output
                and str(exc)
                == "parakeet.cpp C API produced an empty transcript for PCM chunk"
            ):
                self.last_empty_output = True
                return ""
            raise
        return self.runtime._render_unknown_tokens(result)

    def close(self):
        try:
            self.capi.close()
        finally:
            # omi-med-stt 0.2.1 frees its model context, but does not close the
            # Windows AddDllDirectory handles. Repeated per-clip loads exhausted
            # the search-path limit on our first expanded attempt.
            handles = self.capi._dll_directory_handles
            while handles:
                handles.pop().close()
