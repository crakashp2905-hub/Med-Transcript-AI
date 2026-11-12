"""Deterministic PCM quality diagnostics; metrics are not clinical judgments."""

import math
import wave

import numpy as np

from services.api.ingest import file_sha256, inspect_pcm_wav


QUALITY_PROFILE = {
    "schema_version": "audio_quality_v1",
    "frame_ms": 20,
    "silence_threshold_dbfs": -60.0,
    "clipping_threshold_abs_pcm": 32760,
    "sample_jump_threshold_abs_pcm": 30000,
}


def _merge_spans(spans, duration_ms):
    rows = []
    for span in spans or []:
        start, end = span.get("start_ms"), span.get("end_ms")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or end > duration_ms
        ):
            raise ValueError("invalid_quality_annotation_span")
        rows.append((start, end))
    merged = []
    for start, end in sorted(rows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _dbfs(rms):
    return 20 * math.log10(rms / 32768) if rms > 0 else None


def _overlap_frames(spans, first_frame, last_frame, sample_rate):
    for start_ms, end_ms in spans:
        start = max(first_frame, start_ms * sample_rate // 1000)
        end = min(last_frame, (end_ms * sample_rate + 999) // 1000)
        if start < end:
            yield start - first_frame, end - first_frame


def analyze_pcm(path, speech_spans=None, noise_spans=None, profile=QUALITY_PROFILE):
    """Measure clipping, silence, channel balance, jumps and optionally labeled SNR."""
    if profile != QUALITY_PROFILE:
        raise ValueError("unsupported_audio_quality_profile")
    metadata = inspect_pcm_wav(path)
    sample_rate, channels, total_frames = (
        metadata["sample_rate"],
        metadata["channels"],
        metadata["frames"],
    )
    duration_ms = metadata["duration_ms"]
    speech = _merge_spans(speech_spans, duration_ms)
    noise = _merge_spans(noise_spans, duration_ms)
    frame_width = max(1, sample_rate * profile["frame_ms"] // 1000)
    silence_frames = clipping_samples = total_samples = jump_count = largest_jump = 0
    active_channel_energy = np.zeros(channels, dtype=np.float64)
    active_channel_frames = np.zeros(channels, dtype=np.int64)
    speech_energy = noise_energy = 0.0
    speech_samples = noise_samples = 0
    previous = None

    with wave.open(str(path), "rb") as audio:
        frame_index = 0
        while frame_index < total_frames:
            count = min(frame_width, total_frames - frame_index)
            raw = audio.readframes(count)
            values = np.frombuffer(raw, dtype="<i2")
            if values.size != count * channels:
                raise ValueError("corrupt_pcm_frame_data")
            samples = values.reshape(count, channels).astype(np.int32)
            absolute = np.abs(samples)
            clipping_samples += int(
                np.count_nonzero(absolute >= profile["clipping_threshold_abs_pcm"])
            )
            total_samples += int(samples.size)
            if previous is not None:
                delta = np.abs(samples[0] - previous)
                jump_count += int(
                    np.count_nonzero(delta >= profile["sample_jump_threshold_abs_pcm"])
                )
                largest_jump = max(largest_jump, int(delta.max(initial=0)))
            if count > 1:
                delta = np.abs(np.diff(samples, axis=0))
                jumps = delta >= profile["sample_jump_threshold_abs_pcm"]
                jump_count += int(np.count_nonzero(jumps))
                largest_jump = max(largest_jump, int(delta.max(initial=0)))
            previous = samples[-1].copy()

            energy_by_channel = np.sum(samples.astype(np.float64) ** 2, axis=0)
            rms_by_channel = np.sqrt(energy_by_channel / count)
            active = rms_by_channel >= 32768 * 10 ** (
                profile["silence_threshold_dbfs"] / 20
            )
            if not bool(np.any(active)):
                silence_frames += count
            else:
                active_channel_energy[active] += energy_by_channel[active]
                active_channel_frames[active] += count

            for local_start, local_end in _overlap_frames(
                speech, frame_index, frame_index + count, sample_rate
            ):
                block = samples[local_start:local_end].astype(np.float64)
                speech_energy += float(np.sum(block * block))
                speech_samples += int(block.size)
            for local_start, local_end in _overlap_frames(
                noise, frame_index, frame_index + count, sample_rate
            ):
                block = samples[local_start:local_end].astype(np.float64)
                noise_energy += float(np.sum(block * block))
                noise_samples += int(block.size)
            frame_index += count

    silence_ms = silence_frames * 1000 / sample_rate
    channel_rms = [
        math.sqrt(active_channel_energy[index] / active_channel_frames[index])
        if active_channel_frames[index]
        else None
        for index in range(channels)
    ]
    channel_dbfs = [
        _dbfs(value) if value is not None else None for value in channel_rms
    ]
    present_levels = [value for value in channel_dbfs if value is not None]
    imbalance = (
        max(present_levels) - min(present_levels) if len(present_levels) > 1 else None
    )

    snr_db = None
    snr_status = "not_measured_reference_spans_required"
    if speech and noise:
        speech_power = speech_energy / speech_samples if speech_samples else 0
        noise_power = noise_energy / noise_samples if noise_samples else 0
        signal_power = speech_power - noise_power
        if noise_power > 0 and signal_power > 0:
            snr_db = 10 * math.log10(signal_power / noise_power)
            snr_status = "estimated_from_caller_labeled_spans"
        else:
            snr_status = "unavailable_labeled_spans_have_no_positive_signal_estimate"

    return {
        "schema_version": profile["schema_version"],
        "profile": profile,
        "audio_sha256": file_sha256(path),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_ms": duration_ms,
        "clipping_fraction": clipping_samples / total_samples,
        "clipping_samples": clipping_samples,
        "silence_duration_ms": round(silence_ms, 3),
        "silence_fraction": silence_frames / total_frames,
        "silence_threshold_dbfs": profile["silence_threshold_dbfs"],
        "channel_rms_dbfs": channel_dbfs,
        "channel_imbalance_db": imbalance,
        "sample_jump_count": jump_count,
        "largest_sample_jump": largest_jump,
        "snr_db": snr_db,
        "snr_status": snr_status,
        "clinical_interpretation": "not_assessed",
    }
