"""Pinned Omi CPU C API lifecycle for text-only benchmarks, with bounded DLL handles."""

import wave


class OmiPredictor:
    def __init__(self, model_dir, revision):
        import numpy as np
        from omi_stt import cpp_runtime as runtime

        self.np, self.runtime = np, runtime
        model = runtime._download_or_resolve_gguf(str(model_dir), runtime.DEFAULT_GGUF_FILE, revision, True)
        library = runtime._find_parakeet_lib(auto_install=False, backend="cpu")
        self.capi = runtime._ParakeetCAPI(library, model, decoder="tdt", backend="cpu", threads=4)

    def __call__(self, path):
        with wave.open(str(path), "rb") as stream:
            pcm = self.np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
        audio = self.np.ascontiguousarray(pcm.astype(self.np.float32) / 32768.0)
        return self.runtime._render_unknown_tokens(self.capi.transcribe_pcm(audio))

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
