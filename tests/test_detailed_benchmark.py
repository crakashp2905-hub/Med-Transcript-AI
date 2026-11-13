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
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "faster-whisper-large-v3"
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
    assert all(
        "resume_from" not in job and "resume_by_mode" not in job
        for job in suite["jobs"]
    )


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
    assert (
        resource.get("cpu_seconds") is None
    )  # historical report predates CPU receipts


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
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "faster-whisper-large-v3"
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
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v6/whisper-small.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v6.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/whisper-small.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "whisper-small"
    )

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


def test_detailed_v6_whisper_small_overlap_receipt_is_full_and_failure_inclusive():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v6/whisper-small.overlap.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v6.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "whisper-small"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "ee841e73ba7a83cea31a2d7f1077c389991606bfedcd4ce7298584c96b4f5b90"
    )
    assert report["complete"] is True
    assert report["mode"] == "overlap"
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
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["wall_seconds"] > 0
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3


def test_detailed_v7_omi_fixed_receipt_preserves_failures_and_full_resource_scope():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/omi-med-stt-v1.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path(
        "evaluation/experiments/detailed-suite-v7-original-lock-2026-11-13.json"
    )
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "omi-med-stt-v1"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "8d2da60b8e77f8d70ba1bdaff05532904864a8112d9419ba35701d3bc8dad6da"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "omi-med-stt-v1"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert suite["source_text_sha256"]["services/detailed_benchmark.py"] == (
        "3c87b090f17482220173b4830e7b309973290d6e5c087eddeb9cedc871933723"
    )
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert "resume_from" not in job
    assert "resume_by_mode" not in job
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert sum(case["failed"] for case in report["cases"]) == 2
    assert (
        sum(chunk["failed"] for case in report["cases"] for chunk in case["chunks"])
        == 2
    )
    for condition in ("clean", "distracted"):
        observed = report["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 1
        assert observed["reference_words"] == 13683
        assert observed["normalized_wer"] > 0.05
        assert observed["wer_gate"]["status"] == "fail"
        assert observed["wall_seconds"] > 0
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] > 0


def test_detailed_v7_omi_native_empty_fixed_receipt_is_fresh_and_failure_inclusive():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/omi-med-stt-v1-native-empty.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "omi-med-stt-v1-native-empty"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "cfc25c0a8b1334d7a28f357d498eb60ea24aca678c5c688960f551c1f355b68e"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "omi-med-stt-v1-native-empty"
    assert report["suite_sha256"] == hashlib.sha256(suite_path.read_bytes()).hexdigest()
    assert report["manifest_sha256"] == suite["manifest_sha256"]
    assert "resume_from" not in job
    assert "resume_by_mode" not in job
    assert job["allow_native_empty"] is True
    assert {case["id"] for case in report["cases"]} == {
        case["group_id"] for case in manifest["cases"]
    }
    assert len(report["cases"]) == 16
    assert all(not case["failed"] for case in report["cases"])
    assert all(case["input_coverage_complete"] for case in report["cases"])
    assert all(
        not chunk["failed"] for case in report["cases"] for chunk in case["chunks"]
    )
    expected = {
        "clean": (2245, 0.16407220638748812, 1331.6375944999745),
        "distracted": (2356, 0.17218446247168018, 1296.764440900035),
    }
    for condition, (edits, wer, wall) in expected.items():
        observed = report["conditions"][condition]
        assert observed["samples"] == 8
        assert observed["failed_samples"] == 0
        assert observed["reference_words"] == 13683
        assert observed["normalized_edits"] == edits
        assert observed["normalized_wer"] == wer
        assert observed["wall_seconds"] == wall
        assert observed["wer_gate"]["maximum_normalized_wer"] == 0.05
        assert observed["wer_gate"]["status"] == "fail"
    resource = report["resource_measurement"]
    assert resource["status"] == "measured"
    assert resource["cohort_scope"] == "full_process_run"
    assert resource["budget_status"] == "within_budget"
    assert resource["peak_resident_bytes"] == 1265270784
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 9665.71875


def test_detailed_v7_tiny_en_fixed_receipt_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/faster-whisper-tiny.en.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/faster-whisper-tiny.en.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "faster-whisper-tiny.en"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "06da69961c07be44c3de5c72f799a78d031b0748a1231931e483eee0ae7ef6cd"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "faster-whisper-tiny.en"
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
    assert resource["peak_resident_bytes"] == 280338432
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 2043.65625


def test_detailed_v7_whisper_small_fixed_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/whisper-small.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/whisper-small.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "whisper-small"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "07fbb9a170bc49c26a2c69624971db60d0df2587fbad540cd54566800b2e9ba4"
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
    assert resource["peak_resident_bytes"] == 744091648
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 10236.171875


def test_detailed_v7_multimed_fixed_reproduces_negative_baseline_with_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/multimed-whisper-small-english.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/multimed-whisper-small-english.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "multimed-whisper-small-english"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "da396fb055fe4fb975e88de9715c7c033602bbf17e61c38b35f5aee1f34b58f8"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "multimed-whisper-small-english"
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
    assert resource["peak_resident_bytes"] == 650498048
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 12234.5


def test_detailed_v7_parakeet_fixed_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/parakeet-tdt-0.6b-v2.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/parakeet-tdt-0.6b-v2.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "parakeet-tdt-0.6b-v2"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "6aeda83ecafb1f7bfd48eaf7660521ed15ffdc14eeec48ee6babb1fd45333694"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "parakeet-tdt-0.6b-v2"
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
    assert resource["peak_resident_bytes"] == 1300725760
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 4552.734375


def test_detailed_v7_qwen3_fixed_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/qwen3-asr-0.6b-int8.fixed.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/qwen3-asr-0.6b-int8.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item for item in suite["jobs"] if item["candidate_id"] == "qwen3-asr-0.6b-int8"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "2b331885fd7f2639b7345171105f225f6877757e012c0e3eff519085b61d3334"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "qwen3-asr-0.6b-int8"
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
    assert resource["peak_resident_bytes"] == 3058925568
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 19242.78125


def test_detailed_v7_distil_large_v3_fixed_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/distil-whisper-large-v3.fixed-fresh.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/distil-whisper-large-v3.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "distil-whisper-large-v3"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "4652c150c6c5a881eaec8d593d07248a3c3c8688a08ac7b174d8795c84a3726d"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "distil-whisper-large-v3"
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
    assert resource["peak_resident_bytes"] == 1876144128
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 26117.046875


def test_detailed_v7_large_v3_fixed_reproduces_baseline_with_fresh_resources():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/faster-whisper-large-v3.fixed-fresh.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/faster-whisper-large-v3.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "faster-whisper-large-v3"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "5f10f5e4e6cff2630c22a7c12924ca2a2a3f4a7ce28ea747387ff7edb953b52b"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "faster-whisper-large-v3"
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
    assert resource["peak_resident_bytes"] == 3444854784
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 43657.046875


def test_detailed_v7_omi_pinned_refresh_fixed_reproduces_baseline():
    report_path = Path(
        "evaluation/runs/meddistract-detailed-v7/omi-med-stt-v1-native-empty.fixed-pinned-refresh.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    suite_path = Path("evaluation/detailed-suite-v7-omi-pinned-refresh.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    manifest = json.loads(Path(suite["manifest"]).read_text(encoding="utf-8"))
    baseline = json.loads(
        Path(
            "evaluation/runs/meddistract-detailed-v2/omi-med-stt-v1-native-empty.fixed.json"
        ).read_text(encoding="utf-8")
    )
    job = next(
        item
        for item in suite["jobs"]
        if item["candidate_id"] == "omi-med-stt-v1-native-empty"
    )

    assert hashlib.sha256(report_path.read_bytes()).hexdigest() == (
        "5262a13217a2735476058683bf1405bee8662c9a1aa512635a410ebaa1e4a0f9"
    )
    assert report["complete"] is True
    assert report["mode"] == "fixed"
    assert report["candidate_id"] == "omi-med-stt-v1-native-empty"
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
    assert report["runtime"]["allow_native_empty"] is True
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
    assert resource["peak_resident_bytes"] == 1278349312
    assert resource["peak_resident_bytes"] < 16 * 1024**3
    assert resource["cpu_seconds"] == 8951.78125
