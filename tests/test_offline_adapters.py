import pytest

from services.offline_adapters import (
    FakeASRAdapter,
    FakeDiarizationAdapter,
    FakeExtractionAdapter,
    FakeVerifierAdapter,
    SyntheticOnlyError,
)


def test_model_free_adapters_are_deterministic_and_explicitly_synthetic():
    calls = []
    asr = FakeASRAdapter(
        ({"start_seconds": 0, "end_seconds": 1, "text": "No allergy."},)
    )
    result = asr.transcribe(
        "ignored.wav", {"frames": 16000}, lambda: calls.append(None), synthetic=True
    )
    assert result["segments"][0]["text"] == "No allergy."
    assert result["inference_executed"] is False and calls == [None]
    diar = FakeDiarizationAdapter(
        ({"start_ms": 0, "end_ms": 1000, "speaker_id": "speaker_0", "role": "unknown"},)
    )
    assert (
        diar.diarize(None, {}, lambda: None, synthetic=True)["role_assignment"]
        == "clinician_confirmation_required"
    )
    assert (
        FakeExtractionAdapter().extract_facts(
            {"id": "tx"}, authorized=True, synthetic=True
        )["facts"]
        == []
    )
    assert (
        FakeVerifierAdapter().check_claims(
            [{"text": "claim"}], authorized=True, synthetic=True
        )["approval_clearance"]
        == "never"
    )


@pytest.mark.parametrize(
    "adapter,method,args,kwargs",
    [
        (FakeASRAdapter(()), "transcribe", ("ignored", {"frames": 0}), {}),
        (FakeDiarizationAdapter(()), "diarize", (None, {}, lambda: None), {}),
        (
            FakeExtractionAdapter(),
            "extract_facts",
            ({},),
            {"authorized": True, "synthetic": False},
        ),
        (
            FakeVerifierAdapter(),
            "check_claims",
            ([],),
            {"authorized": True, "synthetic": False},
        ),
    ],
)
def test_model_free_adapters_reject_implicit_non_synthetic_use(
    adapter, method, args, kwargs
):
    with pytest.raises(SyntheticOnlyError):
        getattr(adapter, method)(*args, **(kwargs or {}))
