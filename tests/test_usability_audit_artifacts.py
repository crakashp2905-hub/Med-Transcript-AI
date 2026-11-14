import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "evaluation/usability/heuristic-audit-v1.json"
BACKLOG = ROOT / "evaluation/usability/issue-backlog-v1.json"
HEURISTICS = {
    "learnability",
    "discoverability",
    "consistency",
    "feedback",
    "error_recovery",
    "accessibility",
}


def test_heuristic_audit_covers_all_requested_areas_and_labels_scripted_scope():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert {row["heuristic"] for row in audit["observations"]} == HEURISTICS
    assert audit["method"]["human_participants"] == 0
    assert audit["method"]["evidence_class"] == "scripted_local_synthetic_review"
    assert audit["clinical_acceptance"] is False
    assert audit["clinical_release_authorized"] is False
    for path in audit["screenshots"]:
        assert (ROOT / path).is_file()


def test_usability_backlog_has_reproducible_findings_and_acceptance_checks():
    backlog = json.loads(BACKLOG.read_text(encoding="utf-8"))
    assert backlog["items"]
    assert len({item["id"] for item in backlog["items"]}) == len(backlog["items"])
    for item in backlog["items"]:
        assert item["severity"] in {"P0", "P1", "P2", "P3"}
        assert item["impacted_user_story"]
        assert item["reproduction_steps"]
        assert item["acceptance_tests"]
        assert item["screenshot"] in backlog["screenshots"]
        assert (ROOT / item["screenshot"]).is_file()
