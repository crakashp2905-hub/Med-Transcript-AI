import math
import struct
import wave

import pytest

pytest.importorskip("numpy", reason="numpy is required by the VAD candidate")

from services.asr.vad_candidates import detect_file, score_activity


def pcm_with_speech(path):
    sample_rate = 16000
    values = [0] * (sample_rate // 2)
    for index in range(sample_rate // 10, 3 * sample_rate // 10):
        values[index] = round(9000 * math.sin(2 * math.pi * 220 * index / sample_rate))
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        output.writeframes(struct.pack(f"<{len(values)}h", *values))


def test_energy_candidate_returns_versioned_mask_without_changing_audio(tmp_path):
    audio = tmp_path / "synthetic.wav"
    pcm_with_speech(audio)
    original = audio.read_bytes()

    result = detect_file(audio)

    assert result["candidate_id"] == "energy_rms_v1"
    assert len(result["candidate_sha256"]) == 64
    assert result["frame_mask"][:5] == [False] * 5
    assert result["frame_mask"][5:15] == [True] * 10
    assert result["frame_mask"][15:] == [False] * 10
    assert result["speech_intervals_ms"] == [{"start_ms": 60, "end_ms": 340}]
    assert result["score_kind"] == "uncalibrated_energy_heuristic"
    assert result["source_audio_modified"] is False
    assert audio.read_bytes() == original


def test_activity_scoring_reports_missed_and_false_positive_duration():
    scored = score_activity(
        [{"start_ms": 100, "end_ms": 200}],
        [{"start_ms": 50, "end_ms": 150}, {"start_ms": 300, "end_ms": 400}],
        500,
    )

    assert scored["reference_speech_ms"] == 100
    assert scored["overlap_ms"] == 50
    assert scored["missed_speech_ms"] == 50
    assert scored["false_positive_speech_ms"] == 150
    assert scored["false_negative_rate"] == 0.5
    assert scored["false_positive_rate"] == 150 / 400


def test_activity_scorer_unions_overlapping_annotations_and_rejects_bad_spans():
    scored = score_activity(
        [{"start_ms": 10, "end_ms": 40}, {"start_ms": 30, "end_ms": 60}],
        [{"start_ms": 20, "end_ms": 50}],
        100,
    )
    assert scored["reference_speech_ms"] == 50
    assert scored["overlap_ms"] == 30
    with pytest.raises(ValueError, match="invalid_speech_activity_interval"):
        score_activity([{"start_ms": 0, "end_ms": 101}], [], 100)
