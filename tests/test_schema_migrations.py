import pytest

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
