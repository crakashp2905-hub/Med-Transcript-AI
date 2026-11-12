import array

import pytest

from services.asr.energy_vad_chunking import energy_vad_windows


def pcm_with_pause(sample_rate=1000, duration_seconds=35):
    samples = array.array("h", [5000] * (sample_rate * duration_seconds))
    samples[28 * sample_rate : 29 * sample_rate] = array.array("h", [0] * sample_rate)
    return samples.tobytes()


def test_energy_vad_selects_pause_and_preserves_overlapped_source_offsets():
    windows = energy_vad_windows(
        pcm_with_pause(),
        sample_rate=1000,
        target_seconds=30,
        search_seconds=5,
        overlap_seconds=2,
    )

    assert windows[0] == (0, 28500)
    assert windows[-1][1] == 35000
    assert windows[1][0] == 26500
    assert all(end > start for start, end in windows)
    assert all(end - start <= 30000 for start, end in windows)
    assert all(left[1] >= right[0] for left, right in zip(windows, windows[1:]))


def test_energy_vad_uses_nominal_boundary_when_no_low_energy_run_exists():
    samples = array.array("h", [5000] * 35000)
    windows = energy_vad_windows(
        samples.tobytes(),
        sample_rate=1000,
        target_seconds=30,
        search_seconds=5,
        overlap_seconds=2,
    )
    assert windows == [(0, 30000), (28000, 35000)]


@pytest.mark.parametrize(
    ("pcm", "kwargs", "message"),
    [
        (b"\0", {}, "even"),
        (b"\0\0", {"overlap_seconds": 30}, "overlap"),
        (b"\0\0", {"sample_rate": 16001}, "whole_frames"),
    ],
)
def test_energy_vad_rejects_invalid_pcm_or_parameters(pcm, kwargs, message):
    with pytest.raises(ValueError, match=message):
        energy_vad_windows(pcm, **kwargs)


def test_empty_source_has_no_chunks():
    assert energy_vad_windows(b"") == []
