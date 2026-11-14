import pytest

from services.evaluation_metrics import score_text


def test_word_metrics_separate_substitution_deletion_insertion_and_negation():
    result = score_text("Take 5 mg daily, not 10 mg", "Take 5 mg, 10 mg")
    assert result["substitutions"] == 0
    assert result["deletions"] == 2
    assert result["insertions"] == 0
    assert (
        result["word_edits"]
        == result["substitutions"] + result["deletions"] + result["insertions"]
    )
    assert result["wer"] == pytest.approx(2 / 7)


def test_character_error_rate_preserves_decimal_strengths():
    exact = score_text("0.5 mg", "0.5 mg")
    wrong_strength = score_text("0.5 mg", "5 mg")
    assert exact["cer"] == 0
    assert wrong_strength["cer"] > 0


def test_empty_reference_has_undefined_rates_and_limits_large_alignment():
    assert score_text("", "extra words")["wer"] is None
    with pytest.raises(ValueError, match="token_limit"):
        score_text("word " * 10001, "")
