import hashlib
import json
from pathlib import Path
import wave

import pytest

from services.benchmark_ranking import rank, SCORING


@pytest.fixture
def corpus(tmp_path):
    manifest = {"dataset_id": "frozen-test", "samples": [
        {"sample_id": "a", "group_id": "one", "reference": "No drug allergies"},
        {"sample_id": "b", "group_id": "two", "reference": "Dose 0.5 mg"}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"manifest_sha256": digest, "dataset_id": "frozen-test",
        "failure_policy": "empty_hypothesis_full_reference_deletions", "maximum_normalized_wer": .03,
        "allowed_use": "test_only"}))
    report = {"dataset_id": "frozen-test", "manifest_sha256": digest, "scoring_profile": SCORING,
        "failure_policy": "empty_hypothesis_full_reference_deletions", "reference_words": 6,
        "normalized_edits": 0, "failed_samples": 0, "sample_count": 2, "normalized_wer": 0,
        "profile_id": "test-profile", "profile_sha256": "a" * 64, "model_revision": "b" * 40,
        "samples": [{"sample_id": sid, "group_id": group, "reference_words": 3,
            "normalized_edits": 0, "status": "completed", "elapsed_seconds": 1}
            for sid, group in [("a", "one"), ("b", "two")]]}
    return path, lock, report, tmp_path


def execute(corpus, reports):
    path, lock, _, root = corpus
    entries = []
    for cid, report in reports.items():
        (root / f"{cid}.json").write_text(json.dumps(report))
        entries.append({"candidate_id": cid, "status": "completed", "report": f"{cid}.json"})
    return rank(path, lock, entries, root)


def test_equal_scores_share_rank_and_unavailable_models_are_not_ranked(corpus):
    path, lock, report, root = corpus
    result = execute(corpus, {"z": report, "a": report})
    assert [r["rank"] for r in result["ranked"]] == [1, 1]
    blocked = rank(path, lock, [{"candidate_id": "gated", "status": "access_pending", "reason": "No access"}], root)
    assert blocked["ranked"] == [] and "rank" not in blocked["unranked"][0]


@pytest.mark.parametrize("tamper", ["hash", "coverage", "reference", "aggregate", "score"])
def test_incomparable_or_tampered_runs_cannot_enter_ranking(corpus, tamper):
    report = corpus[2]
    if tamper == "hash": report["manifest_sha256"] = "0" * 64
    if tamper == "coverage": report["samples"].pop()
    if tamper == "reference": report["samples"][0]["reference_words"] = 2
    if tamper == "aggregate": report["normalized_edits"] = 1
    if tamper == "score": report["samples"][0]["hypothesis"] = "Patient has allergies"
    result = execute(corpus, {"invalid": report})
    assert not result["ranked"] and result["unranked"][0]["status"] == "invalid_report"


def test_failure_keeps_reference_deletions_and_fails_gate(corpus):
    report = corpus[2]
    report["samples"][0].update(status="failed", normalized_edits=3)
    report.update(failed_samples=1, normalized_edits=3, normalized_wer=.5)
    result = execute(corpus, {"partial": report})
    assert result["ranked"][0]["normalized_wer"] == .5
    assert result["ranked"][0]["wer_gate"]["status"] == "fail"


def test_changed_frozen_manifest_stops_ranking(corpus):
    path, lock, _, root = corpus
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen dataset integrity"):
        rank(path, lock, [], root)


def test_dataset_lock_cannot_relax_user_wer_limit(corpus):
    path, lock, _, root = corpus
    body = json.loads(lock.read_text())
    body["maximum_normalized_wer"] = .1
    lock.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="fixed 3%"):
        rank(path, lock, [], root)


def test_committed_reference_audio_matches_frozen_manifest():
    root = Path(__file__).resolve().parents[1] / "evaluation/datasets/primock57-smoke-v1"
    body = (root / "manifest.json").read_bytes()
    lock = json.loads((root / "lock.json").read_text())
    manifest = json.loads(body)
    assert hashlib.sha256(body).hexdigest() == lock["manifest_sha256"]
    assert len(manifest["samples"]) == lock["sample_count"] == 6
    for sample in manifest["samples"]:
        audio = root / sample["audio"]
        assert hashlib.sha256(audio.read_bytes()).hexdigest() == sample["audio_sha256"]
        with wave.open(str(audio), "rb") as stream:
            assert (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) == (1, 2, 16000)


def test_published_leaderboard_reproduces_from_committed_source_of_truth():
    root = Path(__file__).resolve().parents[1]
    ledger = json.loads((root / "evaluation/benchmark-ledger.json").read_text())
    corpus = root / "evaluation/datasets/primock57-smoke-v1"
    rebuilt = rank(corpus / "manifest.json", corpus / "lock.json", ledger["candidates"], root)
    published = json.loads((root / "evaluation/leaderboard.json").read_text())
    assert rebuilt == published
    assert len(rebuilt["ranked"]) + len(rebuilt["unranked"]) == len(ledger["candidates"])
    assert not any(row["status"] == "invalid_report" for row in rebuilt["unranked"])


def test_every_requested_candidate_has_an_explicit_ledger_entry():
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "evaluation/model-registry.json").read_text())
    ledger = json.loads((root / "evaluation/benchmark-ledger.json").read_text())
    expected = {row["id"] for row in registry["candidates"]} | {registry["integration_fixture"]["id"]}
    assert {row["candidate_id"] for row in ledger["candidates"]} == expected
    assert all(row["status"] not in ("planned", "running", "runtime_audit_running") for row in ledger["candidates"])
