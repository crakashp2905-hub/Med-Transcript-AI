import pytest

from services.asr.risk_selector import assess_span


def span(**updates):
    result = {
        "audio_asset_id": "audio-1",
        "transcript_version": "tx-3",
        "start_ms": 1200,
        "end_ms": 2400,
        "text": "No allergy.",
        "signals": {},
    }
    result.update(updates)
    return result


def test_risk_reasons_are_explicit_source_linked_and_not_probabilities():
    record = assess_span(
        span(
            signals={
                "engine_disagreement": True,
                "invalid_number": False,
                "role_ambiguity": True,
            }
        )
    )
    assert record["risk_reasons"] == ("engine_disagreement", "role_ambiguity")
    assert record["evidence_signals"] == ("engine_disagreement", "role_ambiguity")
    assert record["audio_asset_id"] == "audio-1"
    assert record["transcript_version"] == "tx-3"
    assert record["review_required"] is True
    assert record["risk_score"] is None
    assert record["adopted"] is False


def test_only_measured_silence_with_nonempty_text_is_silence_hallucination():
    assert (
        "silence_hallucination"
        not in assess_span(span(text="", signals={"digital_silence": True}))[
            "risk_reasons"
        ]
    )
    assert (
        assess_span(span(text="", signals={"digital_silence": True}))["risk_reasons"]
        == ()
    )
    assert assess_span(span(text="Take one tablet", signals={"digital_silence": True}))[
        "risk_reasons"
    ] == ("silence_hallucination",)


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"audio_asset_id": ""}, "source_link_required"),
        ({"transcript_version": ""}, "source_link_required"),
        ({"start_ms": True}, "invalid_span"),
        ({"end_ms": 1200}, "invalid_span"),
        ({"signals": {"confidence": 0.98}}, "unsupported_risk_signal"),
        ({"signals": {"uncertain_speech": 1}}, "risk_signals_must_be_boolean"),
    ],
)
def test_invalid_or_untraceable_risk_inputs_fail_closed(updates, code):
    with pytest.raises(ValueError, match=code):
        assess_span(span(**updates))
