import pytest

from services.feature_flags import select
from services.review.providers import (
    DeterministicProvider,
    JSONProvider,
    configured_provider,
)


def test_feature_flag_keeps_deterministic_baseline_by_default():
    result = select()
    assert result["active_method"] == "deterministic"
    assert result["proposed_enabled"] is False


def test_feature_flag_requires_declared_baseline():
    assert select(proposed_enabled=True)["active_method"] == "proposed"
    with pytest.raises(ValueError):
        select(baseline="unknown")


def test_application_provider_keeps_deterministic_baseline_until_explicit_opt_in(
    monkeypatch,
):
    monkeypatch.delenv("MED_TRANSCRIPT_DRAFTING_MODE", raising=False)
    monkeypatch.delenv("MED_TRANSCRIPT_LLM_ENABLED", raising=False)
    assert isinstance(configured_provider(), DeterministicProvider)

    monkeypatch.setenv("MED_TRANSCRIPT_DRAFTING_MODE", "local")
    assert isinstance(configured_provider(), DeterministicProvider)

    monkeypatch.setenv("MED_TRANSCRIPT_LLM_ENABLED", "1")
    provider = configured_provider()
    assert isinstance(provider, JSONProvider)
    assert provider.mode == "local" and provider.enabled is True

    monkeypatch.setenv("MED_TRANSCRIPT_DRAFTING_MODE", "deterministic")
    with pytest.raises(
        ValueError, match="proposed_drafting_requires_local_or_hosted_mode"
    ):
        configured_provider()
