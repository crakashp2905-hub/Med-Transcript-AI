import pytest

from services.clustering_constraints import declare


def test_expected_speaker_count_is_declared_for_development_only():
    result = declare(expected_speakers=2)
    assert (
        result["assumption_declared"] is True
        and result["production_acceptance"] is False
    )


def test_clustering_assumption_cannot_be_used_for_production():
    with pytest.raises(ValueError, match="not_for_production"):
        declare(expected_speakers=2, case_scope="production")
