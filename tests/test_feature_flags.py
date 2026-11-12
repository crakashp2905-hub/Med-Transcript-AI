import pytest

from services.feature_flags import select


def test_feature_flag_keeps_deterministic_baseline_by_default():
    result = select()
    assert result["active_method"] == "deterministic"
    assert result["proposed_enabled"] is False


def test_feature_flag_requires_declared_baseline():
    assert select(proposed_enabled=True)["active_method"] == "proposed"
    with pytest.raises(ValueError):
        select(baseline="unknown")
