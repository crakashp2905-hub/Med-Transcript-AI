from services.keyword_recovery import compare


def test_keyword_recovery_preserves_unsupported_terms_and_requires_selection():
    result = compare(
        {"asr-a": ["aspirin", "inventedterm"], "asr-b": ["aspirin"]}, {"aspirin"}
    )
    assert result["models"]["asr-a"]["unsupported"] == ["inventedterm"]
    assert result["automatic_merge"] is False
    assert result["selection_required"] is True
