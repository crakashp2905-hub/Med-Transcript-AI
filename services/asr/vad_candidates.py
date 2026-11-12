"""Versioned speech-activity candidates, kept separate from ASR routing."""

import hashlib
import json
import wave

from services.api.ingest import file_sha256


ENERGY_RMS_V1 = {
    "schema_version": "speech_activity_candidate_v1",
    "candidate_id": "energy_rms_v1",
    "frame_ms": 20,
    "threshold_dbfs": -38.0,
    "merge_silence_ms": 100,
    "minimum_speech_ms": 60,
    "padding_ms": 40,
}


def candidate_digest(profile=ENERGY_RMS_V1):
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _activity_intervals(mask, frame_ms, duration_ms, profile):
    raw = []
    start = None
    for index, active in enumerate(mask + [False]):
        if active and start is None:
            start = index
        elif not active and start is not None:
            raw.append((start * frame_ms, min(index * frame_ms, duration_ms)))
            start = None

    joined = []
    for start_ms, end_ms in raw:
        if joined and start_ms - joined[-1][1] <= profile["merge_silence_ms"]:
            joined[-1] = (joined[-1][0], end_ms)
        else:
            joined.append((start_ms, end_ms))

    padded = []
    for start_ms, end_ms in joined:
        if end_ms - start_ms < profile["minimum_speech_ms"]:
            continue
        left = max(0, start_ms - profile["padding_ms"])
        right = min(duration_ms, end_ms + profile["padding_ms"])
        if padded and left <= padded[-1][1]:
            padded[-1] = (padded[-1][0], max(padded[-1][1], right))
        else:
            padded.append((left, right))
    return [{"start_ms": start, "end_ms": end} for start, end in padded]


def detect_file(path, profile=ENERGY_RMS_V1):
    """Return an experimental activity mask; never changes or crops the source."""
    if (
        not isinstance(profile, dict)
        or profile.get("schema_version") != "speech_activity_candidate_v1"
    ):
        raise ValueError("unsupported_speech_activity_candidate")
    frame_ms = profile.get("frame_ms")
    threshold_dbfs = profile.get("threshold_dbfs")
    if (
        type(frame_ms) is not int
        or not 5 <= frame_ms <= 100
        or type(threshold_dbfs) not in (int, float)
        or not -90 <= threshold_dbfs <= 0
    ):
        raise ValueError("invalid_speech_activity_profile")
    input_sha256 = file_sha256(path)
    try:
        import numpy as np

        mask = []
        with wave.open(str(path), "rb") as audio:
            channels, width, sample_rate = (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
            )
            if (
                width != 2
                or not 1 <= channels <= 8
                or not 8000 <= sample_rate <= 48000
                or audio.getcomptype() != "NONE"
            ):
                raise ValueError("validated_pcm16_wav_required")
            total_frames = audio.getnframes()
            if total_frames <= 0:
                raise ValueError("empty_speech_activity_audio")
            window_frames = max(1, sample_rate * frame_ms // 1000)
            while True:
                raw = audio.readframes(window_frames)
                if not raw:
                    break
                values = np.frombuffer(raw, dtype="<i2")
                if values.size % channels:
                    raise ValueError("partial_pcm_frame")
                matrix = values.reshape(-1, channels).astype(np.float32)
                rms_per_channel = np.sqrt(np.mean(matrix * matrix, axis=0))
                dbfs = 20 * np.log10(np.maximum(rms_per_channel, 1.0) / 32768.0)
                mask.append(bool(np.max(dbfs) >= threshold_dbfs))
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("invalid_speech_activity_audio") from exc
    if file_sha256(path) != input_sha256:
        raise ValueError("source_audio_changed_during_vad")

    duration_ms = total_frames * 1000 // sample_rate
    effective_profile = {
        **profile,
        "merge_silence_ms": int(profile.get("merge_silence_ms", 0)),
        "minimum_speech_ms": int(profile.get("minimum_speech_ms", 0)),
        "padding_ms": int(profile.get("padding_ms", 0)),
    }
    if any(
        value < 0 or value > 2000
        for value in (
            effective_profile["merge_silence_ms"],
            effective_profile["minimum_speech_ms"],
            effective_profile["padding_ms"],
        )
    ):
        raise ValueError("invalid_speech_activity_profile")
    return {
        "schema_version": profile["schema_version"],
        "candidate_id": profile["candidate_id"],
        "candidate_sha256": candidate_digest(profile),
        "audio_sha256": input_sha256,
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_ms": duration_ms,
        "frame_ms": frame_ms,
        "frame_mask": mask,
        "speech_intervals_ms": _activity_intervals(
            mask, frame_ms, duration_ms, effective_profile
        ),
        "score_kind": "uncalibrated_energy_heuristic",
        "source_audio_modified": False,
    }


def _union(intervals, duration_ms):
    rows = []
    for span in intervals:
        start, end = span.get("start_ms"), span.get("end_ms")
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
            or end > duration_ms
        ):
            raise ValueError("invalid_speech_activity_interval")
        rows.append((start, end))
    merged = []
    for start, end in sorted(rows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def score_activity(reference_intervals, candidate_intervals, duration_ms):
    """Compare time coverage; annotations are accepted only by this scorer."""
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("invalid_audio_duration")
    reference = _union(reference_intervals, duration_ms)
    candidate = _union(candidate_intervals, duration_ms)
    intersection_ms = 0
    i = j = 0
    while i < len(reference) and j < len(candidate):
        intersection_ms += max(
            0,
            min(reference[i][1], candidate[j][1])
            - max(reference[i][0], candidate[j][0]),
        )
        if reference[i][1] <= candidate[j][1]:
            i += 1
        else:
            j += 1
    reference_ms = sum(end - start for start, end in reference)
    candidate_ms = sum(end - start for start, end in candidate)
    missed_ms = reference_ms - intersection_ms
    false_positive_ms = candidate_ms - intersection_ms
    return {
        "reference_speech_ms": reference_ms,
        "candidate_speech_ms": candidate_ms,
        "overlap_ms": intersection_ms,
        "missed_speech_ms": missed_ms,
        "false_positive_speech_ms": false_positive_ms,
        "false_negative_rate": missed_ms / reference_ms if reference_ms else None,
        "false_positive_rate": (
            false_positive_ms / (duration_ms - reference_ms)
            if duration_ms > reference_ms
            else None
        ),
        "rate_denominator_note": "duration rates are time coverage ratios; reference/candidate silence boundaries are not word-level labels",
    }
