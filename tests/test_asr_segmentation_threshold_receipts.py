import hashlib
import json
from pathlib import Path

from services.asr.segmentation_candidate_runner import VAD_THRESHOLD_VARIANTS


RUNS = Path("evaluation/runs/meddistract-detailed-v7/segmentation-candidates")
EXPECTED_SHA256 = {
    "tiny-en-vad-threshold-baseline-v1.json": "db8942abe2a1ae3fb6ff2e6e7c7cb3042e6f353af13411d5bf56a307452884e6",
    "tiny-en-vad-threshold-min-window-2500ms-v1.json": "03094fd4bdf68763c17e2913a82739bc2cf97d683738de80a4e86cd5897013df",
    "tiny-en-vad-threshold-max-window-20000ms-v1.json": "cfd55e74181a5f26712173b6e3649c8d685730df740cb9ad3bce2dc052babd01",
    "tiny-en-vad-threshold-padding-600ms-v1.json": "9036cbff3d7a89cff4b6cae510819de48592d2c087b53666c423ade3e78f12d2",
    "tiny-en-vad-threshold-ablation-v1.json": "52418d14f73b2b039e9f9acceb86967415857c1623296286f53734802af62e4a",
}


def _load(name):
    raw = (RUNS / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256[name]
    return json.loads(raw)


def test_vad_threshold_ablation_receipts_are_matched_and_failure_inclusive():
    names = {
        "baseline": "tiny-en-vad-threshold-baseline-v1.json",
        "min_window_2500ms": "tiny-en-vad-threshold-min-window-2500ms-v1.json",
        "max_window_20000ms": "tiny-en-vad-threshold-max-window-20000ms-v1.json",
        "padding_600ms": "tiny-en-vad-threshold-padding-600ms-v1.json",
    }
    reports = {arm: _load(name) for arm, name in names.items()}
    matrix = _load("tiny-en-vad-threshold-ablation-v1.json")

    assert matrix["complete"] is True
    assert matrix["clinical_acceptance"] is False
    assert matrix["automatic_promotion"] is False
    assert matrix["case_count"] == 16
    assert matrix["reference_words"] == 27366
    assert matrix["wer_admission_maximum"] == 0.05
    assert set(matrix["arms"]) == {"baseline", *VAD_THRESHOLD_VARIANTS}
    assert (
        matrix["generator_source_commit"] == "0d0755cfad61b5f2bdc275e175107bf0892227dd"
    )
    assert matrix["evaluation_source_commits"] == {
        "baseline": "e0d0ecc365a3319818becc2ad3361f137d9ba333",
        "min_window_2500ms": "aeaac6096adea9419b49a78d15078cbc3386ed9b",
        "max_window_20000ms": "aeaac6096adea9419b49a78d15078cbc3386ed9b",
        "padding_600ms": "e0d0ecc365a3319818becc2ad3361f137d9ba333",
    }

    progress = (
        Path("docs/asr-rnd-progress.md").read_text(encoding="utf-8").encode("utf-8")
    )
    ledger = json.loads(Path("evaluation/asr-task-ledger-v3.json").read_text())
    task = next(row for row in ledger["tasks"] if row["id"] == "MTA-ASR-C05")
    assert ledger["progress_record"]["sha256"] == hashlib.sha256(progress).hexdigest()
    assert task["status"] == "EVIDENCE_RECORDED"
    assert task["completion_claim"] is False

    expected_wer = {
        "baseline": 0.34078783892421255,
        "min_window_2500ms": 0.3349777095666155,
        "max_window_20000ms": 0.3508733464883432,
        "padding_600ms": 0.3365124607176789,
    }
    common_sources = None
    first_cases = None
    for arm, report in reports.items():
        summary = report["summary"]
        assert report["complete"] is True
        assert summary["sample_count"] == 16
        assert summary["failed_samples"] == 0
        assert summary["reference_words"] == 27366
        assert summary["normalized_wer"] == expected_wer[arm]
        assert summary["wer_admission"] == "fail"
        assert summary["wer_admission_maximum"] == 0.05
        assert report["resource_measurement"]["status"] == "measured"
        assert matrix["arms"][arm]["receipt_sha256"] == EXPECTED_SHA256[names[arm]]
        sources = report["bindings"]["source_sha256"]
        if common_sources is None:
            common_sources = sources
        else:
            assert sources == common_sources
        identity = [
            (
                row["group_id"],
                row["audio_sha256"],
                row["reference_sha256"],
                row["reference_words"],
            )
            for row in report["cases"]
        ]
        if first_cases is None:
            first_cases = identity
        else:
            assert identity == first_cases
