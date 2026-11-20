import hashlib
import json
from pathlib import Path


RUNS = Path("evaluation/runs/meddistract-detailed-v7/segmentation-candidates")
REPORT_SHA256 = "ba7ce69c6519d2652312027b484927df642ae16c97599cc5f1a7abfee936f7b8"
SOURCE_SHA256 = "8c4cd5496a937961bc6147afb9245ace3b9f58ebb0c7d42ee7955ae0c2d59ae7"


def test_overlap_alignment_receipt_reconciles_same_saved_windows():
    raw = (RUNS / "tiny-en-overlap-sequence-stitch-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    source_path = RUNS / "tiny-en-overlap_aware.json"
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)

    assert report["complete"] is True
    assert report["clinical_acceptance"] is False
    assert report["automatic_promotion"] is False
    assert report["inference_executed"] is False
    assert report["source_receipt_sha256"] == SOURCE_SHA256
    assert hashlib.sha256(source_raw).hexdigest() == SOURCE_SHA256
    assert (
        report["generator_source_commit"] == "3db0c085f2a3197e5184488334d40aff7fc6530f"
    )
    assert report["case_count"] == 16
    assert report["reference_words"] == 27366
    assert report["failed_samples"] == 0
    assert report["wer_admission_maximum"] == 0.05

    exact = report["arms"]["exact_stitch"]
    aligned = report["arms"]["sequence_alignment_stitch"]
    assert exact["normalized_edits"] == 9878
    assert exact["normalized_wer"] == 0.36095885405247385
    assert exact["wer_admission"] == "fail"
    assert aligned["normalized_edits"] == 9853
    assert aligned["normalized_wer"] == 0.36004531170065046
    assert aligned["wer_admission"] == "fail"
    assert aligned["fuzzy_events_requiring_audio_review"] == 5

    source_cases = {row["group_id"]: row for row in source["cases"]}
    assert len(report["cases"]) == 16
    for row in report["cases"]:
        original = source_cases[row["group_id"]]
        assert row["audio_sha256"] == original["audio_sha256"]
        assert row["reference_sha256"] == original["reference_sha256"]
        assert row["exact_stitch_edits"] == original["normalized_edits"]
    assert sum(row["audio_review_required"] for row in report["cases"]) == 5

    progress = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v5.json").read_text())
    task = next(row for row in ledger["tasks"] if row["id"] == "MTA-ASR-C08")
    assert ledger["progress_record"]["sha256"] == hashlib.sha256(progress).hexdigest()
    assert task["status"] == "EVIDENCE_RECORDED"
    assert task["completion_claim"] is False
