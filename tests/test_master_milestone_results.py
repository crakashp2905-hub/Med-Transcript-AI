import json
from pathlib import Path


RESULTS = Path("results")
EXPECTED = {"done", "blockers", "research", "product", "verification"}


def test_milestone_results_are_complete_consistent_and_non_authorizing():
    documents = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in RESULTS.glob("*.json")
    }
    assert set(documents) == EXPECTED
    commits = {document["source_commit"] for document in documents.values()}
    assert len(commits) == 1
    assert all(
        document["clinical_release_authorized"] is False
        for document in documents.values()
    )
    assert documents["blockers"]["blockers"]
    assert documents["research"]["asr_gate"]["maximum_normalized_wer"] == 0.05
    assert documents["research"]["asr_gate"]["promotion_allowed"] is False
    assert documents["verification"]["checks"]["offline_acceptance"]["status"] == "fail"
