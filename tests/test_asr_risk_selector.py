import pytest

from services.asr.risk_selector import assess_span


def evidence(observed, digest):
    return {
        "observed": observed,
        "method": "test_signal_v1",
        "evidence_sha256": digest * 64,
    }


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


def test_risk_reasons_bind_to_diagnostic_digests_not_probabilities():
    record = assess_span(
        span(
            signals={
                "engine_disagreement": evidence(True, "a"),
                "invalid_number": evidence(False, "b"),
                "role_ambiguity": evidence(True, "c"),
            }
        )
    )
    assert record["risk_reasons"] == ("engine_disagreement", "role_ambiguity")
    assert [item["evidence_sha256"] for item in record["evidence_signals"]] == [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    assert record["audio_asset_id"] == "audio-1"
    assert record["transcript_version"] == "tx-3"
    assert record["review_required"] is True
    assert record["risk_score"] is None
    assert record["adopted"] is False


def test_only_measured_silence_with_nonempty_text_is_silence_hallucination():
    measured_silence = {"digital_silence": evidence(True, "d")}
    assert assess_span(span(text="", signals=measured_silence))["risk_reasons"] == ()
    assert assess_span(span(text="Take one tablet", signals=measured_silence))[
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
        ({"signals": {"uncertain_speech": True}}, "risk_signal_provenance_required"),
        (
            {
                "signals": {
                    "uncertain_speech": {
                        "observed": True,
                        "method": "test_signal_v1",
                        "evidence_sha256": "x" * 64,
                    }
                }
            },
            "risk_signal_provenance_required",
        ),
    ],
)
def test_invalid_or_untraceable_risk_inputs_fail_closed(updates, code):
    with pytest.raises(ValueError, match=code):
        assess_span(span(**updates))
