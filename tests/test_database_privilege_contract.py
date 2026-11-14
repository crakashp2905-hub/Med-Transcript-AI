from pathlib import Path

import yaml


def test_compose_uses_a_non_superuser_application_database_role():
    compose = yaml.safe_load(Path("compose.yaml").read_text(encoding="utf-8"))
    db = compose["services"]["db"]
    api = compose["services"]["api"]
    worker = compose["services"]["worker"]

    assert db["environment"]["POSTGRES_USER"] == "medscribe_owner"
    assert "010-create-app-role.sh" in db["volumes"][-1]
    assert (
        "medscribe_app:${MED_TRANSCRIPT_APP_DB_PASSWORD}"
        in api["environment"]["MED_TRANSCRIPT_DB"]
    )
    assert worker["environment"] == api["environment"]

    init_script = Path("deploy/postgres/010-create-app-role.sh").read_text(
        encoding="utf-8"
    )
    assert "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION" in init_script
    assert "GRANT USAGE, CREATE ON SCHEMA public TO medscribe_app" in init_script


def test_operations_runbook_discloses_migration_role_limitation():
    runbook = Path("docs/runbooks/operations.md").read_text(encoding="utf-8")
    assert "not fully separated" in runbook
    assert "one-shot privileged job" in runbook
