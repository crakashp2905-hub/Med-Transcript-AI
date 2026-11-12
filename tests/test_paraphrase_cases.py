from services.paraphrase_cases import scenarios


def test_legitimate_paraphrase_scenarios_are_not_marked_unsafe_by_construction():
    result = scenarios()
    assert len(result) >= 2
    assert all(item["adversarial"] is False for item in result)
    assert result[0]["source"] != result[0]["paraphrase"]
