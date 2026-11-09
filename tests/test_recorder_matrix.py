import pytest

from services.recorder_matrix import matrix


def test_recorder_matrix_covers_required_duration_and_channels():
    result = matrix()
    assert result['duration_minutes'] == 30
    assert result['channels'] == [1, 2, 4, 8]
    assert result['playback_required'] is True and result['synthetic_only'] is True


def test_recorder_matrix_rejects_unbounded_shape():
    with pytest.raises(ValueError):
        matrix(duration_minutes=5)
