import io
import json
import wave
from pathlib import Path

import pytest

pytest.importorskip("numpy", reason="audio replay requires the ASR extra")

import numpy as np

from services.asr.low_volume_adversarial import (
    ATTENUATION_DB,
    RESERVED_GROUPS,
    SAMPLE_ID,
    _attenuate_wav,
)


ROOT = Path(__file__).resolve().parents[1]


def _wav(samples):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return output.getvalue()


def _samples(data):
    with wave.open(io.BytesIO(data), "rb") as audio:
        assert audio.getparams().framerate == 16000
        assert audio.getparams().nchannels == 1
        return np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")


def test_attenuation_preserves_timeline_and_applies_expected_gain():
    source = _wav([12000, -12000] * 1600)
    quieter = _attenuate_wav(source, -20)
    original_samples = _samples(source)
    quieter_samples = _samples(quieter)
    assert len(quieter_samples) == len(original_samples)
    assert np.max(np.abs(quieter_samples.astype(np.int32))) == 1200
    assert _attenuate_wav(source, 0) == source


def test_adversarial_patient_denial_fixture_is_public_and_nonreserved():
    manifest = json.loads(
        (ROOT / "evaluation/datasets/primock57-expanded-v1/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rows = [row for row in manifest["samples"] if row["sample_id"] == SAMPLE_ID]
    assert len(rows) == 1
    row = rows[0]
    assert row["speaker_role"] == "patient"
    assert row["group_id"] not in RESERVED_GROUPS
    assert "not" in row["reference"].lower() and "no" in row["reference"].lower()
    assert ATTENUATION_DB == (0, -12, -20)
