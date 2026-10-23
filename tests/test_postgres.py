"""Runs against an isolated development database in CI; skipped without an explicit DSN."""

import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from services.api.main import Identity, create_app
from services.api.postgres import postgres_migration
from services.api.storage import Store, MIGRATIONS
from tests.test_foundation import headers, payload


def test_postgres_migrations_transform_immutable_triggers():
    sql = postgres_migration(MIGRATIONS[3])
    assert "FOR EACH ROW EXECUTE FUNCTION" in sql
    assert "SELECT RAISE" not in sql
    assert "ON transcript_versions;" in sql


@pytest.mark.skipif(not os.environ.get("MED_TRANSCRIPT_TEST_POSTGRES"), reason="PostgreSQL integration DSN not configured")
def test_real_postgres_encounter_authorization_review(tmp_path):
    dsn = os.environ["MED_TRANSCRIPT_TEST_POSTGRES"]
    credentials = {"a"*40:Identity(tenant_id=uuid4(),clinician_id=uuid4())}
    client = TestClient(create_app(dsn, credentials, str(tmp_path / "assets")))
    body, auth = payload(), headers()
    first = client.post("/v1/encounters", json=body, headers=auth)
    assert first.status_code == 201, first.text
    assert client.post("/v1/encounters", json=body, headers=auth).json() == first.json()
    from tests.test_review_workflow import prepare, draft, approve
    eid, tx, facts = prepare(client, dsn, assets=str(tmp_path / "assets"))
    result = draft(client, eid, tx, facts)
    assert approve(client, eid, result["note"]).status_code == 201
