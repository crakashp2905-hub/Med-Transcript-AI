import types

import pytest

from services.omi_adapter import OmiPredictor


@pytest.mark.parametrize("model_close_fails", [False, True])
def test_native_library_handles_are_closed_even_when_model_cleanup_fails(
    model_close_fails,
):
    closed = []
    handles = [
        types.SimpleNamespace(close=lambda i=i: closed.append(i)) for i in range(8)
    ]

    def close_model():
        if model_close_fails:
            raise RuntimeError("native cleanup failure")

    predictor = OmiPredictor.__new__(OmiPredictor)
    predictor.capi = types.SimpleNamespace(
        close=close_model, _dll_directory_handles=handles
    )
    if model_close_fails:
        with pytest.raises(RuntimeError):
            predictor.close()
    else:
        predictor.close()
    assert sorted(closed) == list(range(8))
    assert handles == []


def test_predictor_opens_only_the_pinned_local_gguf(monkeypatch, tmp_path):
    import sys

    from services import omi_adapter

    model_dir = tmp_path / "model"
    model_dir.mkdir()
    model_file = model_dir / "omi-med-stt-v1-q8_0.gguf"
    model_file.write_bytes(b"local model")
    opened = {}
    runtime = types.SimpleNamespace(
        DEFAULT_GGUF_FILE=model_file.name,
        _find_parakeet_lib=lambda **kwargs: "local-cpu-library",
        _ParakeetCAPI=lambda library, model, **kwargs: opened.update(
            library=library, model=model, kwargs=kwargs
        ),
    )
    monkeypatch.setitem(
        sys.modules, "omi_stt", types.SimpleNamespace(cpp_runtime=runtime)
    )
    monkeypatch.setattr(omi_adapter.importlib.metadata, "version", lambda _: "0.2.1")
    monkeypatch.setattr(
        omi_adapter, "file_sha256", lambda _: omi_adapter.PINNED_GGUF_SHA256
    )

    OmiPredictor(model_dir, omi_adapter.PINNED_REVISION)

    assert opened["library"] == "local-cpu-library"
    assert opened["model"] == str(model_file.resolve())
    assert not hasattr(runtime, "_download_or_resolve_gguf")


def test_predictor_rejects_unpinned_revision_before_runtime_loading(monkeypatch):
    from services import omi_adapter

    monkeypatch.setattr(omi_adapter.importlib.metadata, "version", lambda _: "0.2.1")
    with pytest.raises(ValueError, match="revision is not pinned"):
        OmiPredictor("https://example.invalid/model", "0" * 40)
