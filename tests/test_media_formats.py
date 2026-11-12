from services.media_formats import inspect_format


def test_media_formats_fail_safely_when_codec_is_missing_or_unknown():
    assert inspect_format("wav", codec_available=False)["reason"] == "codec_unavailable"
    assert inspect_format("flac", codec_available=True)["reason"] == "unsupported_codec"


def test_media_formats_accept_available_known_codec():
    result = inspect_format(".webm", codec_available=True)
    assert result["supported"] is True and result["format"] == "webm"
