import pytest

from services.negative_results import record


def test_negative_result_is_preserved_without_modifying_acceptance_materials():
    result = record(method="proposed", baseline="deterministic", outcome="slower")
    assert result["outcome"] == "slower"
    assert result["acceptance_materials_modified"] is False


def test_negative_result_rejects_reserved_material_mutation():
    with pytest.raises(ValueError):
        record(
            method="proposed",
            baseline="deterministic",
            outcome="less_accurate",
            acceptance_materials_modified=True,
        )
