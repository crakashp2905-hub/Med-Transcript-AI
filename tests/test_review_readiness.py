import pytest

from services.review_readiness import status


def test_review_readiness_blocks_drafting_until_source_issues_are_reviewed():
    result = status(unverified_segments=1, uncertain_doses=0, pending_decisions=2)
    assert result['drafting_blocked'] is True
    assert result['unverified_segments'] == 1


def test_review_readiness_allows_clean_source():
    assert status(unverified_segments=0, uncertain_doses=0, pending_decisions=0)['drafting_blocked'] is False
    with pytest.raises(ValueError):
        status(unverified_segments=-1, uncertain_doses=0, pending_decisions=0)
