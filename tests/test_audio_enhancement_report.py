import hashlib
import json
from pathlib import Path


def test_adaptive_gain_paired_report_is_source_bound_and_keeps_gate_unchanged():
    path = Path("evaluation/reports/audio-enhancement-paired-v3.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "554c295d00944cfbd7eaf3f853bc3e2a3f75103289ddc4de2efb94ef4e4801b9"
    )
    assert report["dataset_id"] == "primock57-consultation01-six-utterance-smoke-v1"
    assert report["maximum_normalized_wer"] == 0.05
    assert report["clinical_acceptance"] is False
    assert report["model"]["runtime"] == "omi-med-stt"
    assert report["model"]["empty_output_policy"] == "empty_native_output_is_failure"
    for source, digest in report["source_code_sha256"].items():
        assert hashlib.sha256(Path(source).read_bytes()).hexdigest() == digest

    assert {row["condition_id"] for row in report["conditions"]} == {
        "source_unmodified",
        "rms_level_normalization_v1",
        "adaptive_gain_v1",
        "highpass_80hz_v1",
        "spectral_gate_percentile25_v1",
    }
    for condition in report["conditions"]:
        summary = condition["summary"]
        assert summary["sample_count"] == 6
        assert summary["failed_samples"] == 0
        assert summary["reference_words"] == 134
        assert summary["normalized_edits"] == 9
        assert summary["normalized_wer"] == 9 / 134
        assert summary["admission_gate"]["maximum_normalized_wer"] == 0.05
        assert summary["admission_gate"]["status"] == "fail"
        assert all(sample["status"] == "completed" for sample in condition["samples"])

    for condition in report["conditions"][1:]:
        assert condition["paired_sample_changes"] == {
            "improved_samples": 0,
            "degraded_samples": 0,
            "unchanged_samples": 6,
            "net_normalized_edit_change": 0,
        }
