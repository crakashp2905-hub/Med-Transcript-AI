import pytest

from services.api import storage
from services.domain_contracts import migrate_legacy


@pytest.mark.parametrize(
    "kind", ["transcript", "note", "proposal", "verification", "audit"]
)
def test_schema_migration_is_copy_only_and_stable(kind):
    original = {"id": "synthetic", "schema_version": "legacy-0"}
    migrated = migrate_legacy(kind, original)
    assert migrated == {"id": "synthetic", "schema_version": "1.0"}
    assert original["schema_version"] == "legacy-0"


def test_schema_migration_rejects_unknown_future_version():
    with pytest.raises(ValueError, match="unsupported_schema_version"):
        migrate_legacy("note", {"schema_version": "2.0"})


def test_incomplete_sql_migration_fails_closed_and_rolls_back(tmp_path, monkeypatch):
    path = tmp_path / "malformed.sqlite3"
    original = storage.MIGRATIONS
    monkeypatch.setattr(
        storage, "MIGRATIONS", (*original, "CREATE TABLE incomplete (id INTEGER")
    )

    with pytest.raises(ValueError, match="incomplete_schema_migration_statement"):
        storage.Store(str(path))

    with storage.sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
