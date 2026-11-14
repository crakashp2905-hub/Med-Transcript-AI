from pathlib import Path


def test_operations_playbook_contains_migration_incident_and_stop_procedures():
    text = Path("docs/operations-migration-and-incident-playbook.md").read_text(
        encoding="utf-8"
    )

    required = (
        "## Database migration rehearsal",
        "## Rollback procedure",
        "## Synthetic incident scenarios",
        "## Release stop criteria",
        "lost after the server stored a chunk",
        "matching database/media backup",
        "unchanged 5% ASR gate fails",
        "Do not copy transcripts, audio, access keys, tokens",
    )
    for phrase in required:
        assert phrase in text
