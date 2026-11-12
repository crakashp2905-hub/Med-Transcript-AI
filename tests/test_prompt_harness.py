import pytest

from services.prompt_harness import report


def test_prompt_harness_is_frozen_json_only_and_failure_preserving():
    result = report(
        prompt_digest="p",
        input_digest="i",
        outputs=[{"id": "case", "status": "failed"}],
        failures=["timeout"],
    )
    assert result["json_only"] is True and result["acceptance_data_used"] is False
    assert result["failures"] == ["timeout"]


def test_prompt_harness_rejects_acceptance_only_data():
    with pytest.raises(ValueError, match="acceptance_only_data_forbidden"):
        report(
            prompt_digest="p", input_digest="i", outputs=[], acceptance_data_used=True
        )
