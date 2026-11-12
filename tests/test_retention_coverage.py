from pathlib import Path


def test_retention_path_mentions_auth_live_prefix_drafts_and_model_proposals():
    source = Path("services/maintenance.py").read_text(encoding="utf-8")
    for name in (
        "authorizations",
        "uploads",
        "resume.part",
        "model_proposals",
        "deletion_requests",
        "legal_hold",
    ):
        assert name in source
    tests = Path("tests/test_maintenance.py").read_text(encoding="utf-8")
    assert "post_backup_tombstone" in tests and "reconcile" in tests
