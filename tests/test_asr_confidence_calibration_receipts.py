import hashlib
import json
from pathlib import Path


REPORT = Path("evaluation/runs/asr-confidence-calibration-v2/report.json")
REPORT_SHA256 = "7c08a28ead88cb72cf94f43bf84a0080b03171e4b6b596be6f8bc3dd4efe334f"
SCORE_REPORT_SHA256 = "c33a9498f94f1581004a036d15fe3138d72a7290e18064061f79d0112efaa43a"
SPLIT_SHA256 = "79238bbca18bc009fc3315911dcf6560c907658428cc84abe3f20e51e0842159"


def test_confidence_calibration_is_group_disjoint_and_keeps_gate_unchanged():
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "asr_group_crossfit_confidence_calibration_v1"
    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["asr_model_fit"] is False
    assert report["calibrator_fit"] is True
    assert report["source_commit"] == "bb6a0d1bfd9fc2b9da920239d6fe70258cf50881"
    assert report["recalibration_source_report"] == {
        "path": "evaluation/runs/asr-confidence-calibration-v1/report.json",
        "sha256": SCORE_REPORT_SHA256,
        "inference_rerun": False,
    }

    split_path = Path(report["split_report_path"])
    split_raw = split_path.read_bytes()
    assert hashlib.sha256(split_raw).hexdigest() == SPLIT_SHA256
    split = json.loads(split_raw)
    assignments = split["group_assignments"]
    development = set(assignments["development"])
    reserved = set(assignments["reserved_acceptance"])
    protocol = report["group_protocol"]
    used = set(protocol["calibration_groups_used"])
    assert len(used) == 10
    assert used <= development
    assert not used & reserved
    assert protocol["reserved_acceptance_groups_used"] == []
    assert protocol["training_samples_used_for_calibration"] == 0
    assert protocol["fold_count"] == 10

    metrics = report["metrics"]
    assert metrics["sample_count"] == 60
    assert metrics["scored_sample_count"] == 60
    assert metrics["failed_sample_count"] == 0
    assert metrics["exact_match_count"] == 2
    assert metrics["wer_admission_maximum"] == 0.05
    assert metrics["wer_gate"] == "unchanged_and_not_evaluated_by_calibration"
    assert metrics["out_of_fold_selection"]["selected_samples"] == 0
    assert metrics["uncertainty"]["method"] == (
        "consultation_group_cluster_percentile_bootstrap"
    )
    assert metrics["uncertainty"]["group_count"] == 10

    assert len(report["rows"]) == 60
    for row in report["rows"]:
        held_out = row["consultation_group_id"]
        assert held_out in used
        assert held_out not in row["crossfit_training_groups"]
        assert set(row["crossfit_training_groups"]) == used - {held_out}
        assert "reference" not in row and "hypothesis" not in row

    progress = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v5.json").read_text())
    assert ledger["progress_record"]["sha256"] == hashlib.sha256(progress).hexdigest()
    task = next(task for task in ledger["tasks"] if task["id"] == "MTA-ASR-H07")
    assert task["status"] == "EVIDENCE_RECORDED"
    assert task["completion_claim"] is False
