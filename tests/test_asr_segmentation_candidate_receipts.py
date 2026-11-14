import hashlib
import json
from pathlib import Path


RUNS = Path("evaluation/runs/meddistract-detailed-v7/segmentation-candidates")
EXPECTED = {
    "tiny-en-fixed_window.json": "be008b4f5755520ce1b9a63ea269633439186e2fb1a3c287f9dd2c95d2dd908a",
    "tiny-en-overlap_aware.json": "8c4cd5496a937961bc6147afb9245ace3b9f58ebb0c7d42ee7955ae0c2d59ae7",
    "tiny-en-vad_cut_merge.json": "a2b1d0fdae43d7c3c6f76e37fc902496f44c40555e0c9a2b21c54ecc19cd0cab",
    "tiny-en-pause_aware.json": "6ffeaf7e81e85e825578b0c825af182071982dec962faf384536fd768424652b",
    "tiny-en-segmentation-matrix-v1.json": "c1c2b7c308f3c73687189027268081f67fb6c329e84d420c6ca3ba1cd16aa8cb",
}


def _load(name):
    path = RUNS / name
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED[name]
    return json.loads(raw)


def test_matched_segmentation_receipts_are_immutable_and_gate_inclusive():
    modes = ("fixed_window", "overlap_aware", "vad_cut_merge", "pause_aware")
    reports = {mode: _load(f"tiny-en-{mode}.json") for mode in modes}
    matrix = _load("tiny-en-segmentation-matrix-v1.json")

    assert matrix["complete"] is False
    assert matrix["applicable_modes_complete"] is True
    assert matrix["clinical_acceptance"] is False
    assert matrix["automatic_promotion"] is False
    assert matrix["wer_admission_maximum"] == 0.05
    assert matrix["case_count"] == 16
    assert matrix["channel_first"]["status"] == "not_applicable"

    for mode in modes:
        report = reports[mode]
        assert report["complete"] is True
        assert report["configuration"]["mode"] == mode
        assert report["summary"]["sample_count"] == 16
        assert report["summary"]["failed_samples"] == 0
        assert report["summary"]["wer_admission"] == "fail"
        assert report["summary"]["wer_admission_maximum"] == 0.05
        assert report["resource_measurement"]["status"] == "measured"
        assert len({case["audio_sha256"] for case in report["cases"]}) == 16
        assert all(case["reference_sha256"] for case in report["cases"])
        assert matrix["modes"][mode]["sha256"] == EXPECTED[
            f"tiny-en-{mode}.json"
        ]

    first = reports[modes[0]]["cases"]
    for mode in modes[1:]:
        assert [case["group_id"] for case in reports[mode]["cases"]] == [
            case["group_id"] for case in first
        ]
        assert [case["audio_sha256"] for case in reports[mode]["cases"]] == [
            case["audio_sha256"] for case in first
        ]
        assert [case["reference_sha256"] for case in reports[mode]["cases"]] == [
            case["reference_sha256"] for case in first
        ]
