import hashlib
import json
from pathlib import Path


RUN = Path("evaluation/runs/asr-training-augmentations-v2")
REPORT_SHA256 = "2805f24593b1133fa8deb6a500c0b7ba338682f0d6a31639838e61ce72034f32"
SPLIT_SHA256 = "79238bbca18bc009fc3315911dcf6560c907658428cc84abe3f20e51e0842159"


def test_training_augmentation_receipt_binds_outputs_to_training_split():
    raw = (RUN / "report.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    split_raw = Path(report["split_report_path"]).read_bytes()
    split = json.loads(split_raw)

    assert hashlib.sha256(split_raw).hexdigest() == SPLIT_SHA256
    assert report["split_report_sha256"] == SPLIT_SHA256
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["inference_executed"] is False
    assert report["model_fit"] is False
    assert report["source_commit"] == "c7a9d5e7acb5069611a2d1f19333e5fb1282be8b"
    assert report["parent_training_samples"] == 94
    assert report["parent_training_groups"] == 16
    assert report["augmentation_count"] == 282
    assert report["augmentation_count_by_transform"] == {
        "gain-minus3db": 94,
        "speed-perturb-104pct": 94,
        "synthetic-pink-noise-20db": 94,
    }
    assert report["reserved_acceptance_groups_used"] == []
    assert len(report["limitations"]) == 4
    speed_rows = [
        row
        for row in report["augmentation_rows"]
        if row["transform"] == "speed-perturb-104pct"
    ]
    assert len(speed_rows) == 94
    assert all(row["parameters"]["playback_speed_factor"] == 1.04 for row in speed_rows)
    assert all(
        row["output_frames"] < row["parameters"]["input_frames"] for row in speed_rows
    )

    parent_rows = {
        row["sample_id"]: row for row in split["rows"] if row["split"] == "training"
    }
    assert len(parent_rows) == 94
    assert len(report["augmentation_rows"]) == 282
    assert not any(
        row["parent_consultation_group_id"]
        in {"day5_consultation05", "day5_consultation06", "day5_consultation07"}
        for row in report["augmentation_rows"]
    )
    for row in report["augmentation_rows"]:
        parent = parent_rows[row["source_sample_id"]]
        assert row["split"] == parent["split"] == "training"
        assert row["parent_consultation_group_id"] == parent["consultation_group_id"]
        assert row["parent_audio_sha256"] == parent["audio_sha256"]
        assert row["reference_sha256"] == parent["reference_sha256"]
        assert row["split_inherited_from_parent_group"] is True
        output = RUN / row["augmented_audio_path"]
        assert (
            hashlib.sha256(output.read_bytes()).hexdigest()
            == row["augmented_audio_sha256"]
        )

    progress_raw = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v2.json").read_text())
    assert (
        ledger["progress_record"]["sha256"] == hashlib.sha256(progress_raw).hexdigest()
    )
    assert {
        task_id: task["status"]
        for task_id, task in (
            (task["id"], task)
            for task in ledger["tasks"]
            if task["id"] in {"MTA-ASR-H03", "MTA-ASR-H04"}
        )
    } == {
        "MTA-ASR-H03": "EVIDENCE_RECORDED",
        "MTA-ASR-H04": "EVIDENCE_RECORDED",
    }
    assert all(
        task["completion_claim"] is False
        for task in ledger["tasks"]
        if task["id"] in {"MTA-ASR-H03", "MTA-ASR-H04"}
    )
