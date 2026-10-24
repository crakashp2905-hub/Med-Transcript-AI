import types

import pytest

from services.omi_adapter import OmiPredictor


@pytest.mark.parametrize("model_close_fails", [False, True])
def test_native_library_handles_are_closed_even_when_model_cleanup_fails(model_close_fails):
    closed = []
    handles = [types.SimpleNamespace(close=lambda i=i: closed.append(i)) for i in range(8)]

    def close_model():
        if model_close_fails:
            raise RuntimeError("native cleanup failure")

    predictor = OmiPredictor.__new__(OmiPredictor)
    predictor.capi = types.SimpleNamespace(close=close_model, _dll_directory_handles=handles)
    if model_close_fails:
        with pytest.raises(RuntimeError):
            predictor.close()
    else:
        predictor.close()
    assert sorted(closed) == list(range(8))
    assert handles == []
