import pytest

from services.asr.context_biasing import build_context_bias


def test_context_bias_uses_only_pinned_lexicon_terms_without_text_mutation():
    result = build_context_bias(["PARACETAMOL", "paracetamol"])
    assert result["terms"] == ["paracetamol"]
    assert result["hotwords"] == "paracetamol"
    assert result["candidate_only"] is True
    assert result["text_mutation"] is False


def test_context_bias_rejects_unlisted_term_and_modified_lexicon(tmp_path):
    with pytest.raises(ValueError, match="not_in_pinned_lexicon"):
        build_context_bias(["aspirin"])
    changed = tmp_path / "changed.json"
    changed.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity_failure"):
        build_context_bias(["paracetamol"], changed)
