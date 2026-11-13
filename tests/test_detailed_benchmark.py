import hashlib
import json
import random
import wave
from pathlib import Path

import pytest

from services.detailed_benchmark import (
    coverage,
    evaluate_case,
    fast_score,
    resource_receipt,
    summarize,
)
from services.detailed_benchmark import validated_resume
from services.evaluation import score
from services.prepare_detailed import select
from services.audio_provenance import validate_provenance
from services.api.ingest import file_sha256


def test_resource_receipt_records_cpu_and_honest_peak_memory(monkeypatch):
    monkeypatch.setattr(
        "services.detailed_benchmark.process_peak_resident_bytes",
        lambda: (2048, "test_high_water"),
    )
    receipt = resource_receipt(4096, False, 1.25)
    assert receipt["peak_resident_bytes"] == 2048
    assert receipt["cpu_seconds"] == 1.25
    assert receipt["cpu_scope"] == "benchmark_process_including_model_load"


def test_bitvector_token_scoring_matches_original_normalization_and_edit_counts():
    rng = random.Random(42)
    words = [
        "0.5",
        "5",
        "mg",
        "mcg",
        "no",
        "not",
        "allergy",
        "patient",
        "mother",
        "don't",
        "5-mg",
    ]
    for _ in range(150):
        a = " ".join(rng.choices(words, k=rng.randrange(30)))
        b = " ".join(rng.choices(words, k=rng.randrange(30)))
        assert fast_score(a, b) == score(a, b)
    assert (
        fast_score("no penicillin allergy 0.5 mg", "penicillin allergy 5 mcg")[
            "normalized_edits"
        ]
        == 3
    )


def test_detailed_selection_excludes_reserved_foreground_and_donor():
    rows = [
        {"item_id": "reserved", "donor_id": "safe", "level_db": -10},
        {"item_id": "safe", "donor_id": "reserved", "level_db": -10},
        {"item_id": "other", "donor_id": "safe", "level_db": -5},
        {"item_id": "eligible", "donor_id": "safe", "level_db": -10},
    ]
    assert select(rows, {"reserved"}, 1) == [rows[-1]]
    with pytest.raises(ValueError):
        select(rows, {"reserved"}, 2)


def test_one_failed_window_retains_all_reference_deletions_and_raw_success(tmp_path):
    audio = tmp_path / "source.wav"
    with wave.open(str(audio), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(b"\0\0" * 16000 * 31)
    case = {
        "group_id": "full",
        "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "foreground_id": "patient",
        "condition": "clean",
        "reference_turns": [{"reference": "No penicillin allergy."}],
    }
    calls = []

    def predict(path, context):
        calls.append(context)
        if len(calls) == 2:
            raise RuntimeError("Synthetic native failure")
        return {
            "text": "No penicillin allergy.",
            "segments": [
                {"start_ms": 0, "end_ms": 1000, "text": "No penicillin allergy."}
            ],
        }

    checkpoints = []
    row = evaluate_case(
        case,
        audio,
        predict,
        "fixed",
        lambda current: checkpoints.append(len(current["chunks"])),
    )
    assert (
        row["failed"]
        and row["hypothesis"] == ""
        and row["partial_hypothesis_for_diagnostics_only"] == "No penicillin allergy."
    )
    assert row["normalized_edits"] == row["reference_words"] == 3
    assert row["input_coverage_complete"] and checkpoints == [1, 2]
    assert all(validate_provenance(crop["audio_provenance"]) for crop in row["chunks"])
    assert summarize([row])["wer_gate"]["status"] == "fail"
    assert not row["native_timestamp_bounds_valid"]


def test_coverage_rejects_missing_prefix_gap_or_tail():
    assert coverage([(0, 30), (28, 50)], 50)
    assert not coverage([(1, 30), (28, 50)], 50)
    assert not coverage([(0, 30), (31, 50)], 50)
    assert not coverage([(0, 49)], 50)


def test_resume_rejects_altered_references_models_or_scores():
    from copy import deepcopy

    case = {
        "group_id": "one",
        "condition": "clean",
        "audio_sha256": "a" * 64,
        "reference_turns": [{"reference": "No allergy."}],
    }
    row = {
        "id": "one",
        "condition": "clean",
        "input_sha256": "a" * 64,
        "input_coverage_complete": True,
        "failed": False,
        "reference": "No allergy.",
        "hypothesis": "No allergy.",
        **fast_score("No allergy.", "No allergy."),
    }
    prior = {
        "candidate_id": "model",
        "mode": "fixed",
        "runtime": {"revision": "pinned"},
        "cases": [row],
    }
    assert validated_resume(
        prior, {"cases": [case]}, {"revision": "pinned"}, "model", "fixed"
    ) == [row]
    altered = deepcopy(prior)
    altered["cases"][0]["normalized_edits"] = 1
    with pytest.raises(ValueError):
        validated_resume(
            altered, {"cases": [case]}, {"revision": "pinned"}, "model", "fixed"
        )
    with pytest.raises(ValueError):
        validated_resume(
            prior, {"cases": [case]}, {"revision": "changed"}, "model", "fixed"
        )


def test_detailed_suite_v4_binds_source_and_memory_budget():
    suite_path = "evaluation/detailed-suite-v4.json"
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    predecessor = Path("evaluation/detailed-suite-v3.json")
    assert suite["supersedes_suite"] == predecessor.as_posix()
    assert (
        suite["supersedes_suite_sha256"]
        == hashlib.sha256(predecessor.read_bytes()).hexdigest()
    )
    assert suite["schema_version"] == "detailed_campaign_v2"
    assert suite["maximum_normalized_wer"] == 0.05
    assert suite["resource_budget"]["max_process_resident_bytes"] == 16 * 1024**3
    assert suite["resource_budget"]["models_loaded_simultaneously"] == 1
    assert hashlib.sha256(Path(suite_path).read_bytes()).hexdigest() == (
        "eb273b302226a3355041e8e5947f71d9abed432e735ecdc9745dec17ef48d332"
    )
    assert suite["source_text_sha256"]["services/evaluation.py"] == (
        "73a127a599ee0f3dbaef5e6d3655f56fb55d108e4bd482dc4e6c8aeae374af3f"
    )
    candidate = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "faster-whisper-large-v3"
    )
    resume = candidate["resume_by_mode"]["speech_aware"]
    assert file_sha256(resume["path"]) == resume["sha256"]


def test_detailed_suite_v5_preserves_its_frozen_source_digests():
    suite_path = Path("evaluation/detailed-suite-v5.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    predecessor = Path("evaluation/detailed-suite-v4.json")
    assert suite["supersedes_suite"] == predecessor.as_posix()
    assert suite["supersedes_suite_sha256"] == file_sha256(predecessor)
    assert suite["source_refresh_reason"]
    assert suite["evidence_class_policy"] == "separate_transport_from_measured_asr_v1"
    assert suite["source_text_sha256"]["services/detailed_benchmark.py"] == (
        "cceb5c2c081ff94c6bb09df44810c99454da294e296b38384e296973553be902"
    )


def test_detailed_suite_v6_preserves_source_digests_and_disables_resume():
    suite_path = Path("evaluation/detailed-suite-v6.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    predecessor = Path("evaluation/detailed-suite-v5.json")
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "faster-whisper-large-v3"
    )

    assert suite["supersedes_suite"] == predecessor.as_posix()
    assert suite["supersedes_suite_sha256"] == file_sha256(predecessor)
    assert suite["source_refresh_reason"]
    assert "resume_by_mode" not in job
    assert suite["manifest_sha256"] == file_sha256(suite["manifest"])
    assert suite["maximum_normalized_wer"] == 0.05
    assert suite["source_text_sha256"]["services/detailed_benchmark.py"] == (
        "cceb5c2c081ff94c6bb09df44810c99454da294e296b38384e296973553be902"
    )


def test_detailed_suite_v7_binds_resource_runner_and_requires_fresh_runs():
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    predecessor = Path("evaluation/detailed-suite-v6.json")
    assert suite["supersedes_suite"] == predecessor.as_posix()
    assert suite["supersedes_suite_sha256"] == file_sha256(predecessor)
    assert suite["source_text_sha256"]["services/detailed_benchmark.py"] == file_sha256(
        "services/detailed_benchmark.py"
    )
    assert suite["resource_measurement_policy"]["fresh_run_required"] is True
    assert suite["resource_measurement_policy"]["historical_reuse_permitted"] is False
    assert len(suite["jobs"]) == 9
    assert all("resume_from" not in job and "resume_by_mode" not in job for job in suite["jobs"])


def test_detailed_v4_large_v3_fixed_receipt_is_full_and_reproduces_baseline():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v4/faster-whisper-large-v3.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v4.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/faster-whisper-large-v3.fixed.json"
        ).read_text(encoding="utf-8")
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "05da2b5a3004cc9d91e45acdd857abaf70fc00b0b1586706249d0958b2fa1840"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(not case["failed"] for case in report["cases"])
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert all(
        not chunk["failed"] for case in report["cases"] for chunk in case["chunks"]
    )
    for condition in ("clean", "distracted"):
        observed = report["conditions"][condition]
        frozen = baseline["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["normalized_edits"] == frozen["normalized_edits"]
        assert observed["normalized_wer"] == frozen["normalized_wer"]
        assert observed["wall_seconds"] > 0
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource.get("cpu_seconds") is None  # historical report predates CPU receipts


def test_detailed_v4_large_v3_overlap_receipt_is_full_and_reproduces_baseline():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v4/faster-whisper-large-v3.overlap.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v4.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/faster-whisper-large-v3.overlap.json"
        ).read_text(encoding="utf-8")
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "7a0df4c190b9314126b9dda0ec6f1602dd67d18029e3fd1534071c0833c702ca"
    )
    assert report["complete"] is True
    assert report["mode"] == "overlap"
    assert report["candidate_id"] == "faster-whisper-large-v3"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(not case["failed"] for case in report["cases"])
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert all(
        not chunk["failed"] for case in report["cases"] for chunk in case["chunks"]
    )
    for condition in ("clean", "distracted"):
        observed = report["conditions"][condition]
        frozen = baseline["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["normalized_edits"] == frozen["normalized_edits"]
        assert observed["normalized_wer"] == frozen["normalized_wer"]
        assert observed["wall_seconds"] > 0
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3


def test_detailed_v6_large_v3_speech_aware_receipt_is_fresh_and_full():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v6/faster-whisper-large-v3.speech_aware.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v6.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    prior_full = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v3/faster-whisper-large-v3.speech_aware.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "faster-whisper-large-v3"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "5a7ff8607521bcb0fb1764b358162358e8281f4397e40b01dfe9e4518144c0b9"
    )
    assert report["complete"] is True
    assert report["mode"] == "speech_aware"
    assert report["candidate_id"] == "faster-whisper-large-v3"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert "resume_by_mode" not in job
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(not case["failed"] for case in report["cases"])
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert all(
        not chunk["failed"] for case in report["cases"] for chunk in case["chunks"]
    )
    for condition in ("clean", "distracted"):
        observed = report["conditions"][condition]
        frozen = prior_full["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["normalized_edits"] == frozen["normalized_edits"]
        assert observed["normalized_wer"] == frozen["normalized_wer"]
        assert observed["wall_seconds"] > 0
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3


def test_detailed_v6_whisper_small_fixed_receipt_is_full_and_reproduces_baseline():
    report_path = Path("evaluation/runs/meddistract-detailed-v6/whisper-small.fixed.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v6.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path("evaluation/runs/meddistract-detailed-v2/whisper-small.fixed.json").read_text(
            encoding="utf-8"
        )
    )
    job = next(item for item in suite["jobs"] if item["candidate_id"] == "whisper-small")

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "5ba7cb52dc17d98932790f2456d0975b52da89afed30452cf5d08a808558ff36"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "whisper-small"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert "resume_from" not in job
    assert "resume_by_mode" not in job
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(not case["failed"] for case in report["cases"])
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert all(
        not chunk["failed"] for case in report["cases"] for chunk in case["chunks"]
    )
    for condition in ("clean", "distracted"):
        observed = report["conditions"][condition]
        frozen = baseline["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["normalized_edits"] == frozen["normalized_edits"]
        assert observed["normalized_wer"] == frozen["normalized_wer"]
        assert observed["wall_seconds"] > 0
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3
