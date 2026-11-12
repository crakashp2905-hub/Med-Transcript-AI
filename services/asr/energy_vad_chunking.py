"""Deterministic energy-gated chunk boundaries for offline ASR experiments.

This is a lightweight VAD proxy. It does not use a trained speech model and
must not be described as validated speech detection.
"""

from __future__ import annotations

import array
import math
import sys


def _frame_rms(samples: array.array, frame_samples: int) -> list[float]:
    values = []
    for offset in range(0, len(samples), frame_samples):
        frame = samples[offset : offset + frame_samples]
        if not frame:
            continue
        values.append(math.sqrt(sum(value * value for value in frame) / len(frame)))
    return values


def energy_vad_windows(
    pcm: bytes,
    *,
    sample_rate: int = 16000,
    frame_ms: int = 20,
    target_seconds: int = 30,
    search_seconds: int = 5,
    minimum_silence_ms: int = 200,
    overlap_seconds: int = 2,
    threshold_dbfs: float = -38.0,
) -> list[tuple[int, int]]:
    """Return overlapping sample-offset windows with full source coverage.

    Chunk boundaries are moved to the midpoint of qualifying low-energy runs
    near the nominal boundary. A hard target limit bounds each ASR request.
    The offsets are start-inclusive/end-exclusive sample indices.
    """
    if sample_rate <= 0 or frame_ms <= 0 or sample_rate * frame_ms % 1000:
        raise ValueError("sample_rate_and_frame_ms_must_form_whole_frames")
    if target_seconds <= 0 or search_seconds < 0 or minimum_silence_ms <= 0:
        raise ValueError("chunk_timing_parameters_invalid")
    if overlap_seconds < 0 or overlap_seconds >= target_seconds:
        raise ValueError("overlap_must_be_nonnegative_and_shorter_than_target")
    if len(pcm) % 2:
        raise ValueError("pcm_s16le_byte_length_must_be_even")

    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    total = len(samples)
    if total == 0:
        return []

    frame_samples = sample_rate * frame_ms // 1000
    rms = _frame_rms(samples, frame_samples)
    threshold = 32768 * (10 ** (threshold_dbfs / 20))
    silent = [level < threshold for level in rms]
    silence_frames = math.ceil(minimum_silence_ms / frame_ms)
    search_frames = search_seconds * 1000 // frame_ms
    target = target_seconds * sample_rate
    hard_limit = target
    overlap = overlap_seconds * sample_rate

    windows: list[tuple[int, int]] = []
    start = 0
    while start < total:
        nominal_end = min(total, start + target)
        if nominal_end == total:
            end = total
        else:
            nominal_frame = nominal_end // frame_samples
            lower = max(start // frame_samples, nominal_frame - search_frames)
            upper = min(len(silent), nominal_frame + search_frames)
            candidates: list[int] = []
            index = lower
            while index < upper:
                if not silent[index]:
                    index += 1
                    continue
                run_start = index
                while index < upper and silent[index]:
                    index += 1
                if index - run_start >= silence_frames:
                    midpoint = (run_start + index) // 2
                    candidate = midpoint * frame_samples
                    if start < candidate <= start + hard_limit:
                        candidates.append(candidate)
            end = min(
                candidates,
                key=lambda point: (abs(point - nominal_end), point),
                default=nominal_end,
            )
            end = min(end, start + hard_limit)
        if end <= start:
            raise ValueError("chunk_boundary_did_not_advance")
        windows.append((start, end))
        if end == total:
            break
        next_start = max(start + 1, end - overlap)
        start = next_start

    if windows[0][0] != 0 or windows[-1][1] != total:
        raise ValueError("source_coverage_incomplete")
    if any(end <= start for start, end in windows):
        raise ValueError("empty_chunk")
    if any(end - start > target for start, end in windows):
        raise ValueError("chunk_exceeds_target_limit")
    if any(left[1] < right[0] for left, right in zip(windows, windows[1:])):
        raise ValueError("source_coverage_gap")
    return windows
