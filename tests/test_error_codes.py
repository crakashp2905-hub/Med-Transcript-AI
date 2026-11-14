from services.error_codes import ERROR_CATALOG, ErrorCode, public_error


def test_error_codes_have_stable_non_sensitive_public_mapping():
    result = public_error(ErrorCode.ASR_FAILED)
    assert result == {"error_code": "asr_failed", "message": "asr failed"}
    assert "token" not in result["message"] and "secret" not in result["message"]


def test_unknown_error_does_not_echo_input():
    result = public_error("secret-token-and-audio")
    assert result["error_code"] == "internal_error"
    assert "secret-token-and-audio" not in str(result)


def test_catalog_is_the_source_for_every_public_error():
    assert ERROR_CATALOG["schema_version"] == "med_transcript_error_catalog_v1"
    assert ERROR_CATALOG["fallback"] in ERROR_CATALOG["errors"]
    for code, entry in ERROR_CATALOG["errors"].items():
        assert public_error(code) == {
            "error_code": code,
            "message": entry["message"],
        }
