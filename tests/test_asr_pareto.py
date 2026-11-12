import hashlib
import json

import pytest

pytest.importorskip("rapidfuzz")

from services.asr.pareto import run


def _write_suite(path, candidates):
    path.write_text(
        json.dumps({"jobs": [{"candidate_id": candidate} for candidate in candidates]}),
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(candidate, suite_sha256, hypothesis, *, failed=False, latency=2.0):
    return {
        "schema_version": "detailed_full_asr_v1",
        "candidate_id": candidate,
        "manifest_sha256": "a" * 64,
        "suite_sha256": suite_sha256,
        "mode": "fixed",
        "complete": True,
        "model_load_seconds": 1.0,
        "cases": [
            {
                "id": "case",
                "foreground_id": "consult",
                "condition": "clean",
                "input_sha256": "b" * 64,
                "input_coverage_complete": True,
                "reference": "patient denies fever",
                "hypothesis": "" if failed else hypothesis,
                "failed": failed,
                "normalized_edits": 3 if failed else 1,
                "reference_words": 3,
                "wall_seconds": latency,
                "chunks": [{"end_ms": 10000}],
            }
        ],
    }


def test_pareto_report_pairs_engines_retains_failures_and_unknown_memory(tmp_path):
    candidates = ["engine-a", "engine-b"]
    suite = tmp_path / "suite.json"
    suite_hash = _write_suite(suite, candidates)
    paths = []
    for candidate, hypothesis, failed in (
        ("engine-a", "patient denies fever", False),
        ("engine-b", "", True),
    ):
        path = tmp_path / f"{candidate}.json"
        path.write_text(
            json.dumps(
                _report(candidate, suite_hash, hypothesis, failed=failed, latency=2)
            ),
            encoding="utf-8",
        )
        paths.append(str(path))
    result = run(paths, suite, tmp_path / "pareto.json")
    pair = result["two_engine_rover"][0]
    assert pair["failed_samples"] == 1
    assert pair["reference_words"] == 3
    assert pair["maximum_process_memory_bytes"] is None
    assert result["targeted_fallback"]["status"] == "not_evaluated"


def test_pareto_rejects_different_source_audio(tmp_path):
    suite = tmp_path / "suite.json"
    suite_hash = _write_suite(suite, ["a", "b"])
    paths = []
    for candidate in ("a", "b"):
        report = _report(candidate, suite_hash, "patient denies fever")
        if candidate == "b":
            report["cases"][0]["input_sha256"] = "c" * 64
        path = tmp_path / f"{candidate}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(str(path))
    with pytest.raises(ValueError, match="matched_audio_reference_coverage_required"):
        run(paths, suite, tmp_path / "pareto.json")
