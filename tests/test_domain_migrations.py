import json
from copy import deepcopy
from pathlib import Path

import pytest

from services.domain_contracts import (
    MIGRATION_REGISTRY,
    MODELS,
    migrate_legacy,
    validate_record,
)


FIXTURES = Path(__file__).parent / "fixtures" / "domain_records"


def test_every_registered_record_kind_has_explicit_legacy_and_current_migrations():
    assert set(MIGRATION_REGISTRY) == set(MODELS)
    assert all(
        set(paths) == {"legacy-0", "1.0"} for paths in MIGRATION_REGISTRY.values()
    )


def test_historical_saved_note_migrates_copy_only_and_remains_readable():
    legacy = json.loads((FIXTURES / "legacy_note_v0.json").read_text(encoding="utf-8"))
    original = deepcopy(legacy)

    migrated = migrate_legacy("note", legacy)
    validated = validate_record("note", legacy)

    assert legacy == original
    assert migrated["schema_version"] == "1.0"
    assert {
        key: value for key, value in migrated.items() if key != "schema_version"
    } == original
    assert validated.version == 1
    assert validated.facts[0].text == "Cough"
    assert validated.sections[0].statements[0].evidence.quote == "Cough"


def test_current_saved_note_is_copied_without_rewriting_and_future_versions_fail():
    legacy = json.loads((FIXTURES / "legacy_note_v0.json").read_text(encoding="utf-8"))
    current = {**legacy, "schema_version": "1.0"}
    before = deepcopy(current)

    migrated = migrate_legacy("note", current)

    assert migrated == before
    assert current == before
    assert validate_record("note", current).version == 1
    with pytest.raises(ValueError, match="unsupported_schema_version"):
        migrate_legacy("note", {**current, "schema_version": "2.0"})
    with pytest.raises(ValueError, match="unsupported_record_kind"):
        migrate_legacy("unknown", current)
