import pytest

from services.provider_interfaces import (
    ASRProvider, DiarizationProvider, DraftingProvider, ExtractionProvider,
    VerificationProvider, require_limitations,
)


def test_all_provider_interfaces_are_declared():
    assert all(cls is not None for cls in (ASRProvider, DiarizationProvider, DraftingProvider, ExtractionProvider, VerificationProvider))
    assert require_limitations(type('Result', (), {'limitations': ['local-only']})())


def test_provider_result_without_limitations_is_rejected():
    with pytest.raises(ValueError, match='provider_limitations_required'):
        require_limitations(type('Result', (), {'limitations': []})())
