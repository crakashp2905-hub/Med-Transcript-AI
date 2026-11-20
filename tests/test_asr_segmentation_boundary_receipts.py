import hashlib
import json
from pathlib import Path


RUNS = Path("evaluation/runs/meddistract-detailed-v7/segmentation-candidates")
MATRIX_SHA256 = "5b1ab354a7a79e0a7156fa6c079487fe156d608d463d5081e3c3a99369d95bbf"
MODE_SHA256 = {
    "fixed_window": "be008b4f5755520ce1b9a63ea269633439186e2fb1a3c287f9dd2c95d2dd908a",
    "overlap_aware": "8c4cd5496a937961bc6147afb9245ace3b9f58ebb0c7d42ee7955ae0c2d59ae7",
    "vad_cut_merge": "a2b1d0fdae43d7c3c6f76e37fc902496f44c40555e0c9a2b21c54ecc19cd0cab",
    "pause_aware": "6ffeaf7e81e85e825578b0c825af182071982dec962faf384536fd768424652b",
}


def test_segmentation_boundary_receipt_is_complete_and_scope_limited():
    path = RUNS / "tiny-en-segmentation-boundary-diagnostics-v1.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MATRIX_SHA256
    report = json.loads(raw)

    assert report["schema_version"] == "asr_segmentation_boundary_matrix_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["case_count"] == 16
    assert report["turn_time_mapping"]["short_turn_threshold_ms"] == 100
    assert (
        report["boundary_metric_scope"]
        == "reference_turn_interval_intersections_not_word_alignment"
    )
    assert report["receipt_commit_status"] == "not_recorded_in_original_mode_receipts"
    assert (
        report["generator_source_commit"] == "cd2bb123702350ba4451dfeaedcebda91c5a42df"
    )

    expected = {
        "fixed_window": (304, 320, 326),
        "overlap_aware": (454, 340, 344),
        "vad_cut_merge": (251, 482, 534),
        "pause_aware": (300, 322, 330),
    }
    first_identity = None
    for mode, (clipped, joined, windows) in expected.items():
        result = report["modes"][mode]
        summary = result["summary"]
        assert result["receipt_sha256"] == MODE_SHA256[mode]
        assert result["source_commit"] is None
        assert summary["annotated_turns"] == 2168
        assert summary["omitted_short_turns"] == 0
        assert summary["clipped_turns"] == clipped
        assert summary["partially_uncovered_turns"] == 0
        assert summary["windows_joining_known_roles"] == joined
        assert summary["windows_with_unknown_role_turns"] == 0
        assert summary["segmentation_windows"] == windows
        assert len(result["files"]) == 16
        identity = [
            (row["group_id"], row["audio_sha256"], row["reference_sha256"])
            for row in result["files"]
        ]
        if first_identity is None:
            first_identity = identity
        else:
            assert identity == first_identity
        assert all(
            "reference" not in turn and "text" not in turn
            for file_row in result["files"]
            for turn in file_row["turns"]
        )

    assert any(
        "do not measure word-edge timing error" in item
        for item in report["limitations"]
    )
    assert any(
        "not independently adjudicated clinical gold" in item
        for item in report["limitations"]
    )

    progress = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v2.json").read_text())
    task = next(row for row in ledger["tasks"] if row["id"] == "MTA-ASR-C06")
    assert ledger["progress_record"]["sha256"] == hashlib.sha256(progress).hexdigest()
    assert task["status"] == "PARTIAL"
    assert task["completion_claim"] is False
