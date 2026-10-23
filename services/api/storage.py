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
    """
    CREATE TABLE asr_profiles (sha256 TEXT PRIMARY KEY, body TEXT NOT NULL);
    CREATE TABLE jobs_next (
        id TEXT PRIMARY KEY, upload TEXT NOT NULL REFERENCES uploads(id),
        encounter TEXT NOT NULL REFERENCES encounters(id),
        status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
        attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT, lease_expires_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error_code TEXT, result TEXT,
        stage TEXT NOT NULL DEFAULT 'audio_ingest' CHECK(stage IN ('audio_ingest','transcription')),
        profile_sha256 TEXT REFERENCES asr_profiles(sha256));
    INSERT INTO jobs_next (id,upload,encounter,status,attempts,lease_token,lease_expires_at,
        created_at,updated_at,error_code,result)
        SELECT id,upload,encounter,status,attempts,lease_token,lease_expires_at,
        created_at,updated_at,error_code,result FROM jobs;
    DROP TABLE jobs;
    ALTER TABLE jobs_next RENAME TO jobs;
    CREATE INDEX jobs_claim ON jobs(stage,status,created_at);
    CREATE UNIQUE INDEX jobs_ingest_upload ON jobs(upload) WHERE stage='audio_ingest';
    CREATE UNIQUE INDEX jobs_transcription_input ON jobs(upload,profile_sha256) WHERE stage='transcription';
    CREATE TABLE transcript_versions (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        upload TEXT NOT NULL REFERENCES uploads(id), job TEXT NOT NULL UNIQUE REFERENCES jobs(id),
        version INTEGER NOT NULL, sha256 TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(encounter,version));
    CREATE TRIGGER transcript_versions_immutable BEFORE UPDATE ON transcript_versions
    BEGIN
        SELECT RAISE(ABORT, 'Transcript versions are immutable');
    END;
    """,
    """
    ALTER TABLE encounters ADD COLUMN current_transcript TEXT;
    ALTER TABLE encounters ADD COLUMN current_note TEXT;
    ALTER TABLE encounters ADD COLUMN deleted_at TEXT;
    ALTER TABLE encounters ADD COLUMN legal_hold INTEGER NOT NULL DEFAULT 0;
    DROP TRIGGER transcript_versions_immutable;
    CREATE TABLE transcripts_next (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        upload TEXT NOT NULL REFERENCES uploads(id), job TEXT UNIQUE REFERENCES jobs(id),
        version INTEGER NOT NULL, sha256 TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(encounter,version));
    INSERT INTO transcripts_next SELECT * FROM transcript_versions;
    DROP TABLE transcript_versions;
    ALTER TABLE transcripts_next RENAME TO transcript_versions;
    CREATE TRIGGER transcript_versions_immutable BEFORE UPDATE ON transcript_versions
    BEGIN
        SELECT RAISE(ABORT, 'Transcript versions are immutable');
    END;
    UPDATE encounters SET current_transcript=(SELECT id FROM transcript_versions
        WHERE encounter=encounters.id ORDER BY version DESC LIMIT 1);
    CREATE TABLE documents (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        kind TEXT NOT NULL CHECK(kind IN ('note','verification')), version INTEGER NOT NULL,
        sha256 TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(encounter,kind,version));
    CREATE TRIGGER documents_immutable BEFORE UPDATE ON documents
    BEGIN
        SELECT RAISE(ABORT, 'Document versions are immutable');
    END;
    CREATE TABLE approvals (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        note TEXT NOT NULL UNIQUE REFERENCES documents(id), body TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE exports (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL REFERENCES encounters(id),
        approval TEXT NOT NULL REFERENCES approvals(id), format TEXT NOT NULL,
        artifact TEXT NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(approval,format));
    CREATE TABLE deletion_requests (
        id TEXT PRIMARY KEY, encounter TEXT NOT NULL UNIQUE REFERENCES encounters(id),
        status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
    """,
)


class Store:
    def __init__(self, path: str):
        self.path = path
        self.backend = None
        if path.startswith(("postgresql://", "postgres://")):
            from services.api.postgres import PostgresStore
            self.backend = PostgresStore(path, MIGRATIONS)
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as con:
            current = con.execute("PRAGMA user_version").fetchone()[0]
            if current > len(MIGRATIONS):
                raise RuntimeError("Database schema is newer than this application")
            for version, migration in enumerate(MIGRATIONS, start=1):
                if version > current:
                    statement = ""
                    for line in migration.splitlines(keepends=True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            con.execute(statement)
                            statement = ""
                    con.execute(f"PRAGMA user_version={version}")

    @contextmanager
    def transaction(self):
        if self.backend:
            with self.backend.transaction() as con:
                yield con
            return
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
    row = con.execute("SELECT deleted_at FROM encounters WHERE id=?", (str(encounter_id),)).fetchone()
    if row is None or row["deleted_at"]:
        return False
    return {"recording", "local_processing"} <= active_scopes(con, encounter_id)


def default_asset_root(db):
    return "data/assets" if db.startswith(("postgresql://", "postgres://")) else str(Path(db).parent / "assets")
