import hashlib
import json
from pathlib import Path


RUNS = Path("evaluation/runs/meddistract-detailed-v7/segmentation-candidates")
REPORT_SHA256 = "4ff8ccec752a799d1ed406aeba9a66aa34838ce712e9a512dc5753ed003b0cdf"
RECEIPT_SHA256 = {
    "fixed_window": "be008b4f5755520ce1b9a63ea269633439186e2fb1a3c287f9dd2c95d2dd908a",
    "overlap_aware": "8c4cd5496a937961bc6147afb9245ace3b9f58ebb0c7d42ee7955ae0c2d59ae7",
    "vad_cut_merge": "a2b1d0fdae43d7c3c6f76e37fc902496f44c40555e0c9a2b21c54ecc19cd0cab",
    "pause_aware": "6ffeaf7e81e85e825578b0c825af182071982dec962faf384536fd768424652b",
}


def test_segmentation_source_map_receipt_covers_all_saved_native_segments():
    raw = (RUNS / "tiny-en-segmentation-source-maps-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)

    assert report["schema_version"] == "asr_segmentation_source_map_matrix_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["inference_executed"] is False
    assert report["case_count"] == 16
    assert report["native_segment_count"] == 9875
    assert (
        report["generator_source_commit"] == "d8ff0897ad9e7db09622e111ce0b13963ffadfd0"
    )
    assert report["source_frame_mapping"]["sample_rate"] == 16000
    assert "never clamp" in report["source_frame_mapping"]["invalid_native_timestamps"]

    expected = {
        "fixed_window": (2478, 2321, 157),
        "overlap_aware": (2619, 2486, 133),
        "vad_cut_merge": (2302, 2171, 131),
        "pause_aware": (2476, 2350, 126),
    }
    common_cases = None
    for mode, values in expected.items():
        result = report["modes"][mode]
        summary = result["summary"]
        assert result["receipt_sha256"] == RECEIPT_SHA256[mode]
        assert summary["native_segments"] == values[0]
        assert summary["mapped_segments"] == values[1]
        assert summary["invalid_window_timestamps"] == values[2]
        assert summary["round_trip_failures"] == 0
        case_identity = [
            (row["group_id"], row["audio_sha256"], row["reference_sha256"])
            for row in result["files"]
        ]
        if common_cases is None:
            common_cases = case_identity
        else:
            assert case_identity == common_cases
        for file_row in result["files"]:
            for segment in file_row["segments"]:
                assert segment["window_id"] in segment["segment_id"]
                assert "text" not in segment
                if segment["source_timestamp_in_window"]:
                    assert segment["source_start_frame"] is not None
                    assert segment["source_end_frame_exclusive"] is not None
                    assert segment["source_round_trip_valid"] is True
                else:
                    assert segment["source_start_frame"] is None
                    assert segment["source_end_frame_exclusive"] is None
                    assert segment["source_round_trip_valid"] is False


def test_source_map_progress_record_is_hash_bound_and_stays_partial():
    ledger_path = Path("evaluation/asr-task-ledger-v1.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    progress_path = Path(ledger["progress_record"]["path"])
    assert (
        hashlib.sha256(progress_path.read_bytes()).hexdigest()
        == ledger["progress_record"]["sha256"]
    )
    task = next(row for row in ledger["tasks"] if row["id"] == "MTA-ASR-C09")
    assert task["status"] == "PARTIAL"
    assert task["completion_claim"] is False
