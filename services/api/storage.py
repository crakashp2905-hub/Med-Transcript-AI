"""Versioned development storage shared by API and local ingest worker."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS encounters (
        id TEXT PRIMARY KEY, tenant TEXT NOT NULL, clinician TEXT NOT NULL,
        body TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS authorizations (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        body TEXT NOT NULL, created_at TEXT NOT NULL, withdrawn_at TEXT);
    CREATE TABLE IF NOT EXISTS audit (
        id TEXT PRIMARY KEY, tenant TEXT NOT NULL, actor TEXT NOT NULL,
        action TEXT NOT NULL, resource TEXT NOT NULL, time TEXT NOT NULL);
    """,
    """
    CREATE TABLE idempotency (
        tenant TEXT NOT NULL, actor TEXT NOT NULL, operation TEXT NOT NULL,
        key_hash TEXT NOT NULL, fingerprint TEXT NOT NULL, response TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        PRIMARY KEY (tenant, actor, operation, key_hash));
    CREATE TABLE uploads (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        expected_bytes INTEGER NOT NULL, expected_sha256 TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('open','uploading','uploaded','complete')),
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE TABLE jobs (
        id TEXT PRIMARY KEY, upload TEXT NOT NULL UNIQUE REFERENCES uploads(id),
        encounter TEXT NOT NULL REFERENCES encounters(id),
        status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
        attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_expires_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        error_code TEXT, result TEXT);
    CREATE INDEX jobs_claim ON jobs(status, created_at);
    CREATE INDEX authorizations_encounter ON authorizations(encounter);
    """,
)


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as con:
            current = con.execute("PRAGMA user_version").fetchone()[0]
            if current > len(MIGRATIONS):
                raise RuntimeError("Database schema is newer than this application")
            for version, migration in enumerate(MIGRATIONS, start=1):
                if version > current:
                    for statement in migration.split(";"):
                        if statement.strip():
                            con.execute(statement)
                    con.execute(f"PRAGMA user_version={version}")

    @contextmanager
    def transaction(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            # Serialize read-check-write operations, including duplicate retries.
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()


def active_scopes(con, encounter_id):
    rows = con.execute("SELECT body FROM authorizations WHERE encounter=? AND withdrawn_at IS NULL",
                       (str(encounter_id),)).fetchall()
    scopes = set()
    for row in rows:
        body = json.loads(row["body"])
        if datetime.fromisoformat(body["expires_at"]) > datetime.now(timezone.utc):
            scopes.update(body["scopes"])
    return scopes


def processing_allowed(con, encounter_id):
    return {"recording", "local_processing"} <= active_scopes(con, encounter_id)
