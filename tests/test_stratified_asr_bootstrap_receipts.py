import hashlib
import json
from pathlib import Path


REPORT = Path("evaluation/reports/paired-asr-stratified-bootstrap-v2.json")
REPORT_SHA256 = "6d29a962427c94d8387c7230bf37819b49cf85f44ebba5fecc2697555c1cd2b7"
RESERVED = {"day5_consultation05", "day5_consultation06", "day5_consultation07"}


def test_stratified_bootstrap_receipt_binds_sources_and_keeps_failures():
    raw = REPORT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_SHA256
    report = json.loads(raw)
    assert report["schema_version"] == "paired_asr_stratified_bootstrap_v1"
    assert report["complete"] is True
    assert report["inference_executed"] is False
    assert report["analysis_only_replay"] is True
    assert report["clinical_acceptance"] is False
    assert report["candidate_count"] == 9
    assert report["protocol"]["resampling_unit"] == "foreground_consultation_group"
    assert report["protocol"]["iterations"] == 10000
    assert report["protocol"]["maximum_normalized_wer"] == 0.05
    assert report["protocol"]["primary_wer_modified"] is False
    groups = set(report["protocol"]["consultation_groups"])
    assert len(groups) == 8
    assert not groups & RESERVED

    inputs = report["inputs"]
    assert inputs["manifest_sha256"] == (
        "d0c4e960d013668d5cb21eb0d40b8a500d6fe545643564d31ffb9be13c77c262"
    )
    assert (
        hashlib.sha256(
            Path("evaluation/reports/paired-asr-bootstrap-v1.json").read_bytes()
        ).hexdigest()
        == inputs["paired_report_sha256"]
    )
    assert (
        hashlib.sha256(
            Path("evaluation/reports/error-taxonomy-v2/report.json").read_bytes()
        ).hexdigest()
        == inputs["taxonomy_report_sha256"]
    )

    failed_pairs = 0
    for candidate in report["candidates"]:
        assert candidate["case_count"] == 16
        assert candidate["consultation_group_count"] == 8
        overall = candidate["overall_recording_condition_delta"]
        assert overall["paired_foregrounds"] == 8
        assert overall["failed_pairs_excluded"] == 0
        failed_pairs += overall["failed_pairs_included"]
        assert set(candidate["speaker_role_strata"]) == {"clinician", "patient"}
        for role in candidate["speaker_role_strata"].values():
            interval = role["paired_interval"]
            assert interval["consultation_groups"] == 8
            assert interval["iterations"] == 10000
            assert interval["low"] <= interval["high"]
        assert len(candidate["literal_clinical_term_strata"]) == 16
        for term in candidate["literal_clinical_term_strata"].values():
            interval = term["paired_interval"]
            if interval is None:
                continue
            assert interval["consultation_groups"] >= 1
            if interval["consultation_groups"] == 1:
                assert interval["low"] is None and interval["high"] is None
                assert interval["interval_method"].startswith("not_estimable_")
            else:
                assert interval["low"] <= interval["high"]
    assert failed_pairs == 1

    progress = Path("docs/asr-rnd-progress.md").read_bytes()
    ledger = json.loads(Path("evaluation/asr-task-ledger-v1.json").read_text())
    assert ledger["progress_record"]["sha256"] == hashlib.sha256(progress).hexdigest()
    task = next(task for task in ledger["tasks"] if task["id"] == "MTA-ASR-I07")
    assert task["status"] == "EVIDENCE_RECORDED"
    assert task["completion_claim"] is False
