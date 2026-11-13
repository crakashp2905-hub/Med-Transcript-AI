"""Source-preserving boundary for experimental audio enhancement candidates."""

import os
from pathlib import Path
import shutil
import tempfile
import wave

import numpy as np

from services.audio_provenance import (
    derive_provenance,
    file_sha256,
    source_provenance,
)


def _read_mono_pcm16(path):
    with wave.open(str(path), "rb") as audio:
        if (
            audio.getnchannels(),
            audio.getsampwidth(),
            audio.getcomptype(),
        ) != (1, 2, "NONE"):
            raise ValueError("enhancement_requires_mono_pcm16_wav")
        rate = audio.getframerate()
        if not 8000 <= rate <= 48000:
            raise ValueError("unsupported_enhancement_sample_rate")
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
    if samples.size == 0:
        raise ValueError("empty_enhancement_input")
    return samples.astype(np.float64), rate


def _write_mono_pcm16(path, samples, sample_rate):
    samples = np.clip(np.rint(samples), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        audio.writeframes(samples.tobytes())


def normalize_rms_transform(target_dbfs=-23.0, peak_ceiling=0.98):
    if not -50 <= target_dbfs <= -6 or not 0.1 <= peak_ceiling <= 1:
        raise ValueError("invalid_rms_normalization_profile")

    def transform(source, output):
        samples, rate = _read_mono_pcm16(source)
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms <= 0:
            raise ValueError("cannot_normalize_silent_audio")
        target_rms = 32768 * 10 ** (target_dbfs / 20)
        gain = min(
            target_rms / rms, peak_ceiling * 32767 / float(np.max(np.abs(samples)))
        )
        _write_mono_pcm16(output, samples * gain, rate)

    return transform


def adaptive_gain_transform(
    target_dbfs=-24.0,
    maximum_boost_db=12.0,
    maximum_cut_db=12.0,
    silence_floor_dbfs=-50.0,
    frame_ms=100,
    hop_ms=50,
    attack_seconds=0.25,
    release_seconds=0.1,
    peak_ceiling=0.98,
):
    """Apply bounded short-time RMS gain with a silence floor and peak limiter."""
    if (
        not -50 <= target_dbfs <= -6
        or not 0 <= maximum_boost_db <= 24
        or not 0 <= maximum_cut_db <= 24
        or not -90 <= silence_floor_dbfs <= -10
        or not 20 <= frame_ms <= 1000
        or not 10 <= hop_ms <= frame_ms
        or attack_seconds <= 0
        or release_seconds <= 0
        or not 0.1 <= peak_ceiling <= 1
    ):
        raise ValueError("invalid_adaptive_gain_profile")

    def transform(source, output):
        samples, rate = _read_mono_pcm16(source)
        frame = max(1, round(rate * frame_ms / 1000))
        hop = max(1, round(rate * hop_ms / 1000))
        centers, desired_db = [], []
        floor_rms = 32768 * 10 ** (silence_floor_dbfs / 20)
        target_rms = 32768 * 10 ** (target_dbfs / 20)
        for start in range(0, samples.size, hop):
            end = min(samples.size, start + frame)
            if end - start < frame // 2 and centers:
                break
            rms = float(np.sqrt(np.mean(samples[start:end] ** 2)))
            if rms <= floor_rms:
                gain_db = 0.0
            else:
                gain_db = 20 * np.log10(target_rms / rms)
                gain_db = float(np.clip(gain_db, -maximum_cut_db, maximum_boost_db))
            centers.append((start + end - 1) / 2)
            desired_db.append(gain_db)

        smoothed_db = [desired_db[0]]
        for desired in desired_db[1:]:
            previous = smoothed_db[-1]
            time_constant = attack_seconds if desired > previous else release_seconds
            alpha = np.exp(-hop / (rate * time_constant))
            smoothed_db.append(alpha * previous + (1 - alpha) * desired)
        gain = 10 ** (
            np.interp(
                np.arange(samples.size),
                centers,
                smoothed_db,
                left=smoothed_db[0],
                right=smoothed_db[-1],
            )
            / 20
        )
        output_samples = samples * gain
        peak = float(np.max(np.abs(output_samples)))
        if peak:
            output_samples *= min(1.0, peak_ceiling * 32767 / peak)
        _write_mono_pcm16(output, output_samples, rate)

    return transform


def highpass_transform(cutoff_hz=80, order=4):
    if type(cutoff_hz) is not int or not 20 <= cutoff_hz <= 500:
        raise ValueError("invalid_highpass_profile")
    if type(order) is not int or not 1 <= order <= 8:
        raise ValueError("invalid_highpass_profile")

    def transform(source, output):
        from scipy.signal import butter, sosfiltfilt

        samples, rate = _read_mono_pcm16(source)
        if cutoff_hz >= rate / 2:
            raise ValueError("highpass_cutoff_exceeds_nyquist")
        sos = butter(order, cutoff_hz, btype="highpass", fs=rate, output="sos")
        filtered = sosfiltfilt(sos, samples)
        _write_mono_pcm16(output, filtered, rate)

    return transform


def spectral_gate_transform(
    noise_percentile=25, threshold_multiplier=1.5, minimum_gain=0.15
):
    if (
        type(noise_percentile) is not int
        or not 5 <= noise_percentile <= 50
        or not 1 <= threshold_multiplier <= 5
        or not 0 <= minimum_gain <= 1
    ):
        raise ValueError("invalid_spectral_gate_profile")

    def transform(source, output):
        from scipy.signal import istft, stft

        samples, rate = _read_mono_pcm16(source)
        frequencies, times, spectrum = stft(
            samples,
            fs=rate,
            window="hann",
            nperseg=512,
            noverlap=384,
            boundary="zeros",
            padded=True,
        )
        magnitude = np.abs(spectrum)
        noise_floor = np.percentile(magnitude, noise_percentile, axis=1, keepdims=True)
        threshold = noise_floor * threshold_multiplier
        gain = np.maximum(minimum_gain, 1 - threshold / np.maximum(magnitude, 1e-12))
        _, restored = istft(
            spectrum * gain,
            fs=rate,
            window="hann",
            nperseg=512,
            noverlap=384,
            input_onesided=True,
            boundary=True,
        )
        if restored.size < samples.size:
            restored = np.pad(restored, (0, samples.size - restored.size))
        _write_mono_pcm16(output, restored[: samples.size], rate)

    return transform


def prepare_candidate(
    source_path,
    candidate_path=None,
    enhancement_id=None,
    transform=None,
    parameters=None,
    timeline_mapping=None,
):
    """Return source audio unchanged or publish a distinct derived candidate."""
    source = Path(source_path).resolve()
    source_receipt = source_provenance(source)
    original_sha256 = source_receipt["asset_sha256"]
    if enhancement_id is None:
        if any(
            value is not None for value in (transform, parameters, timeline_mapping)
        ):
            raise ValueError("disabled_enhancement_cannot_accept_transform")
        return {
            "candidate_path": str(source),
            "candidate_sha256": original_sha256,
            "enhancement_id": "disabled",
            "enhancement_applied": False,
            "audio_provenance": source_receipt,
        }

    if (
        not isinstance(enhancement_id, str)
        or not enhancement_id.strip()
        or not callable(transform)
        or not isinstance(parameters, dict)
        or not isinstance(timeline_mapping, dict)
        or candidate_path is None
    ):
        raise ValueError("incomplete_enhancement_candidate")
    target = Path(candidate_path).resolve()
    if target == source or target.exists():
        raise ValueError("enhancement_candidate_must_be_a_new_file")
    if not target.parent.is_dir():
        raise ValueError("enhancement_candidate_directory_required")

    staging = snapshot = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".audio-candidate-",
            suffix=target.suffix or ".wav",
            dir=target.parent,
            delete=False,
        ) as temporary:
            staging = Path(temporary.name)
        with tempfile.NamedTemporaryFile(
            prefix=".audio-source-snapshot-",
            suffix=source.suffix or ".wav",
            dir=target.parent,
            delete=False,
        ) as temporary:
            snapshot = Path(temporary.name)
        shutil.copyfile(source, snapshot)
        if file_sha256(snapshot) != original_sha256:
            raise ValueError("source_snapshot_integrity_failure")
        transform(snapshot, staging)
        if not staging.is_file() or staging.stat().st_size == 0:
            raise ValueError("enhancement_candidate_output_required")
        if file_sha256(source) != original_sha256:
            raise ValueError("source_audio_changed_during_enhancement")
        if file_sha256(snapshot) != original_sha256:
            raise ValueError("enhancement_input_snapshot_changed")
        receipt = derive_provenance(
            source_receipt,
            staging,
            enhancement_id,
            parameters,
            timeline_mapping,
        )
        os.rename(staging, target)
        staging = None
        if file_sha256(target) != receipt["asset_sha256"]:
            target.unlink(missing_ok=True)
            raise ValueError("enhancement_candidate_changed_after_publish")
        return {
            "candidate_path": str(target),
            "candidate_sha256": receipt["asset_sha256"],
            "enhancement_id": enhancement_id,
            "enhancement_applied": True,
            "source_sha256": original_sha256,
            "audio_provenance": receipt,
        }
    finally:
        if staging is not None:
            staging.unlink(missing_ok=True)
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)
