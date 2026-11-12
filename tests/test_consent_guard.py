import pytest

from services.consent_guard import STAGES, evaluate


def test_revocation_blocks_every_processing_stage_and_publication():
    for stage in STAGES:
        result = evaluate(revoked=True, stage=stage)
        assert result["allowed"] is False
        assert result["publication_blocked"] is True


def test_unknown_consent_stage_is_rejected():
    with pytest.raises(ValueError):
        evaluate(revoked=False, stage="unknown")
