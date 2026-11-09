import pytest

from services.asr.chunk_selection import freeze_strategy


def test_chunk_selection_is_frozen_before_scoring():
    result = freeze_strategy('fixed_30s', {'seconds': 30})
    assert result['frozen_before_scoring'] is True
    assert result['hypothesis_used_for_selection'] is False


def test_chunk_selection_rejects_oracle_or_unknown_strategy():
    with pytest.raises(ValueError, match='oracle_free_selection_required'):
        freeze_strategy('pause_aware', {'pause_ms': 400}, scored=True)
