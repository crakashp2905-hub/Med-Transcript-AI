from array import array
import hashlib
import wave
from types import SimpleNamespace

from services.asr.matched_ablation_runner import ENERGY_VAD_CONFIG, _decode, _run_case


class FakeWhisper:
    def __init__(self):
        self.calls = []

    def transcribe(self, samples, **options):
        self.calls.append(options)
        duration = len(samples) / 16000
        segment = SimpleNamespace(start=0.0, end=duration, text="Warfarin 2.5 mg daily")
        return iter([segment]), SimpleNamespace(language="en")


def _source(tmp_path):
    path = tmp_path / "case.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(array("h", [10000] * 32000).tobytes())
    return path


def _case(path):
    return {
        "group_id": "consultation-a",
        "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "condition": "clean",
        "foreground_id": "consultation-a",
        "donor_id": None,
        "reference_turns": [{"reference": "Warfarin 2.5 mg daily"}],
    }


def test_repair_arm_redecodes_source_bound_risk_spans_as_unadopted_candidates(
    tmp_path,
):
    source = _source(tmp_path)
    model = FakeWhisper()

    row = _run_case(model, _case(source), source, "repair_only", 5, None, None)

    assert row["hypothesis"] == "Warfarin 2.5 mg daily"
    assert len(row["repair_candidates"]) == 1
    assert row["repair_candidates"][0]["review_required"] is True
    assert row["repair_candidates"][0]["adopted"] is False
    assert len(model.calls) == 2
    assert all(call["beam_size"] == 5 for call in model.calls)


def test_full_pipeline_uses_energy_vad_decoder_hotwords_and_bounded_repair(tmp_path):
    source = _source(tmp_path)
    model = FakeWhisper()

    row = _run_case(
        model,
        _case(source),
        source,
        "full_pipeline",
        1,
        "warfarin",
        ENERGY_VAD_CONFIG,
    )

    assert row["vad_interval_count"] == 1
    assert row["vad_missed_all_speech"] is False
    assert row["repair_candidates"][0]["adopted"] is False
    assert len(model.calls) == 2
    assert all(call["beam_size"] == 1 for call in model.calls)
    assert model.calls[0]["hotwords"] == "warfarin"


def test_decoder_timestamps_are_clamped_to_the_source_crop():
    model = FakeWhisper()
    row = _decode(model, b"\x00\x00" * 16100, 100, 16100, beam_size=5)

    assert row[0]["start_frame"] == 100
    assert row[0]["end_frame"] == 16100
