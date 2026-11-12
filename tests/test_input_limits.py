from services.input_limits import validate


def test_input_limits_reject_expensive_or_oversized_inputs():
    result = validate(
        request_bytes=30_000_000,
        audio_seconds=10,
        json_depth=2,
        decompressed_bytes=1,
        timestamp_seconds=0,
        stage="asr",
    )
    assert result["accepted"] is False
    assert "request_size" in result["rejection_reasons"]


def test_input_limits_accept_bounded_request():
    assert (
        validate(
            request_bytes=10,
            audio_seconds=10,
            json_depth=2,
            decompressed_bytes=10,
            timestamp_seconds=0,
            stage="asr",
        )["accepted"]
        is True
    )
