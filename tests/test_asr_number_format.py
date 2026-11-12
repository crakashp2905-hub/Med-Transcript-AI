from services.asr.number_format import propose_quantity_format


def test_quantity_spacing_and_unit_case_change_preserve_value_and_unit():
    result = propose_quantity_format("Take 0.5MG daily.")
    assert result["formatted_candidate"] == "Take 0.5 mg daily."
    assert result["quantity_signature_preserved"] is True
    assert result["unit_added"] is False
    assert result["automatic_adoption"] is False


def test_formatter_never_invents_missing_or_unsupported_units():
    for text in ("Take 5 daily.", "Take 5 micrograms daily."):
        result = propose_quantity_format(text)
        assert result["formatted_candidate"] == text
        assert result["unit_added"] is False


def test_formatter_preserves_decimal_and_literal_unit_distinctions():
    result = propose_quantity_format("0.5 mg, 5 mcg")
    assert result["formatted_candidate"] == "0.5 mg, 5 mcg"
    assert result["automatic_adoption"] is False
