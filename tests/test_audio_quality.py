import math
import random
import wave

import pytest

from services.asr.audio_quality import analyze_pcm


def write_wav(path, values, channels=1, sample_rate=16000):
    import numpy as np

    interleaved = np.asarray(values, dtype="<i2").reshape(-1, channels)
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, 2, sample_rate, 0, "NONE", "not compressed"))
        output.writeframes(interleaved.tobytes())


def test_reports_silence_and_clipping_deterministically(tmp_path):
    silence = tmp_path / "silence.wav"
    clipped = tmp_path / "clipped.wav"
    write_wav(silence, [0] * 16000)
    write_wav(clipped, [32767] * 16000)

    silent_report = analyze_pcm(silence)
    clip_report = analyze_pcm(clipped)

    assert silent_report["silence_duration_ms"] == 1000
    assert silent_report["silence_fraction"] == 1
    assert silent_report["clipping_fraction"] == 0
    assert silent_report["snr_status"] == "not_measured_reference_spans_required"
    assert clip_report["clipping_fraction"] == 1
    assert clip_report["clipping_samples"] == 16000


def test_reports_channel_imbalance_and_sample_jumps(tmp_path):
    stereo = tmp_path / "imbalanced.wav"
    samples = [[8192, 819] for _ in range(16000)]
    write_wav(stereo, samples, channels=2)
    jumps = tmp_path / "jumps.wav"
    jump_signal = [8192] * 16000
    jump_signal[8000] = -24000
    write_wav(jumps, jump_signal)

    channel_report = analyze_pcm(stereo)
    jump_report = analyze_pcm(jumps)

    assert channel_report["channel_imbalance_db"] == pytest.approx(20, abs=0.1)
    assert jump_report["sample_jump_count"] == 2
    assert jump_report["largest_sample_jump"] == 32192
    assert channel_report["clinical_interpretation"] == "not_assessed"


def test_snr_uses_only_explicit_speech_and_noise_spans(tmp_path):
    rng = random.Random(73)
    sample_rate = 16000
    noise = [rng.randint(-250, 250) for _ in range(sample_rate)]
    values = noise.copy()
    for index in range(sample_rate // 2):
        values[index] += round(8000 * math.sin(2 * math.pi * 220 * index / sample_rate))
    audio = tmp_path / "speech-and-noise.wav"
    write_wav(audio, values)

    unlabelled = analyze_pcm(audio)
    measured = analyze_pcm(
        audio,
        speech_spans=[{"start_ms": 0, "end_ms": 500}],
        noise_spans=[{"start_ms": 500, "end_ms": 1000}],
    )

    assert unlabelled["snr_db"] is None
    assert measured["snr_status"] == "estimated_from_caller_labeled_spans"
    assert measured["snr_db"] > 25


def test_quality_analysis_rejects_invalid_annotation_spans(tmp_path):
    audio = tmp_path / "clip.wav"
    write_wav(audio, [0] * 16000)
    with pytest.raises(ValueError, match="invalid_quality_annotation_span"):
        analyze_pcm(audio, speech_spans=[{"start_ms": 900, "end_ms": 1100}])
