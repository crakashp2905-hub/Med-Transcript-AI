import hashlib
import json

import pytest

pytest.importorskip("rapidfuzz")

from services.asr.rover import rover_vote, run
from services.evaluation import score
from services.asr.rover import _score


def test_fast_rover_score_matches_frozen_primary_scorer():
    reference = "The patient denies fever and takes 0.5 mg."
    hypothesis = "Patient has fever; takes 5 mg."
    assert _score(reference, hypothesis) == score(reference, hypothesis)


def test_rover_majority_votes_tokens_and_never_emits_confidence():
    vote = rover_vote(
        [
            {"backend_id": "pivot", "text": "patient denies fever"},
            {"backend_id": "second", "text": "patient has fever"},
            {"backend_id": "third", "text": "patient has fever"},
        ],
        "pivot",
    )
    assert vote["text"] == "patient has fever"
    assert vote["confidence"] is None
    assert vote["clinical_truth_asserted"] is False


def test_rover_ties_favor_the_declared_pivot():
    vote = rover_vote(
        [
            {"backend_id": "pivot", "text": "takes 5 mg"},
            {"backend_id": "other", "text": "takes 15 mg"},
        ],
        "pivot",
    )
    assert vote["text"] == "takes 5 mg"
    assert any(row["tie_break"] == "pivot" for row in vote["confusion_network"])


def _report(candidate, hypothesis, suite_sha256, failed=False):
    return {
        "schema_version": "detailed_full_asr_v1",
        "candidate_id": candidate,
        "manifest_sha256": "a" * 64,
        "suite_sha256": suite_sha256,
        "mode": "fixed",
        "complete": True,
        "cases": [
            {
                "id": "consult-a",
                "foreground_id": "consult-a",
                "condition": "clean",
                "input_sha256": "c" * 64,
                "input_coverage_complete": True,
                "failed": failed,
                "reference": "Patient denies fever",
                "hypothesis": "" if failed else hypothesis,
            }
        ],
    }


def _suite(tmp_path, candidates):
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps({"jobs": [{"candidate_id": item} for item in candidates]}),
        encoding="utf-8",
    )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_rover_evaluation_pairs_audio_and_keeps_failed_backend_in_denominator(
    tmp_path,
):
    candidates = ("pivot", "second", "third")
    suite_path, suite_sha256 = _suite(tmp_path, candidates)
    inputs = []
    for candidate, hypothesis, failed in (
        ("pivot", "patient denies fever", False),
        ("second", "patient has fever", False),
        ("third", "", True),
    ):
        path = tmp_path / f"{candidate}.json"
        path.write_text(
            json.dumps(_report(candidate, hypothesis, suite_sha256, failed)),
            encoding="utf-8",
        )
        inputs.append(str(path))
    output = tmp_path / "rover.json"
    result = run(inputs, output, "pivot", suite_path)
    assert result["rover_summary"]["reference_words"] == 3
    assert result["rover_summary"]["failed_samples"] == 1
    assert result["cases"][0]["candidate_failed"]
    assert result["rover_admission"] == "not_admitted"


def test_rover_rejects_mismatched_sources(tmp_path):
    suite_path, suite_sha256 = _suite(tmp_path, ("one", "two"))
    reports = [
        _report("one", "hello", suite_sha256),
        _report("two", "hello", suite_sha256),
    ]
    reports[1]["cases"][0]["input_sha256"] = "d" * 64
    paths = []
    for index, report in enumerate(reports):
        path = tmp_path / f"{index}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(str(path))
    with pytest.raises(ValueError, match="paired_audio_reference_or_coverage_mismatch"):
        run(paths, tmp_path / "out.json", "one", suite_path)
