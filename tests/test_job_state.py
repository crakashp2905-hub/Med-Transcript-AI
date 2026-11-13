import sqlite3

from services.api.job_state import (
    pending_transcription_capacity,
    request_cancellation,
)


def _database():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE encounters (id TEXT PRIMARY KEY, tenant TEXT NOT NULL);
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, encounter TEXT NOT NULL, stage TEXT NOT NULL,
            status TEXT NOT NULL, error_code TEXT, lease_token TEXT,
            lease_expires_at TEXT, updated_at TEXT
        );
        """
    )
    return con


def test_pending_asr_queue_is_bounded_per_tenant(monkeypatch):
    con = _database()
    monkeypatch.setenv("MED_TRANSCRIPT_MAX_PENDING_ASR_JOBS", "2")
    con.executemany(
        "INSERT INTO encounters VALUES (?,?)",
        [("e1", "t1"), ("e2", "t1"), ("e3", "t2")],
    )
    con.executemany(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
        [
            ("j1", "e1", "transcription", "queued", None, None, None, "now"),
            ("j2", "e2", "transcription", "running", None, None, None, "now"),
            ("j3", "e3", "transcription", "queued", None, None, None, "now"),
            ("j4", "e1", "audio_ingest", "queued", None, None, None, "now"),
            ("j5", "e1", "transcription", "failed", None, None, None, "now"),
        ],
    )

    assert not pending_transcription_capacity(con, "t1")
    assert pending_transcription_capacity(con, "t2")


def test_invalid_queue_capacity_fails_closed(monkeypatch):
    con = _database()
    for value in ("0", "257", "many"):
        monkeypatch.setenv("MED_TRANSCRIPT_MAX_PENDING_ASR_JOBS", value)
        assert not pending_transcription_capacity(con, "tenant")


def test_running_job_cancellation_is_cooperative_and_idempotent():
    con = _database()
    con.execute("INSERT INTO encounters VALUES ('e1','t1')")
    con.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
        ("j1", "e1", "transcription", "running", None, "lease", "later", "old"),
    )

    assert request_cancellation(con, "j1", "cancel-time") == "cancelled"
    job = con.execute("SELECT * FROM jobs WHERE id='j1'").fetchone()
    assert job["error_code"] == "cancelled_by_user"
    assert job["lease_token"] is None and job["lease_expires_at"] is None
    assert job["updated_at"] == "cancel-time"
    assert request_cancellation(con, "j1", "retry-time") == "cancelled"
    assert (
        con.execute("SELECT updated_at FROM jobs WHERE id='j1'").fetchone()[0]
        == "cancel-time"
    )


def test_terminal_jobs_are_not_rewritten_by_cancellation():
    con = _database()
    con.execute("INSERT INTO encounters VALUES ('e1','t1')")
    con.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
        ("j1", "e1", "transcription", "succeeded", None, None, None, "done"),
    )

    assert request_cancellation(con, "j1", "cancel-time") == "succeeded"
    assert (
        con.execute("SELECT updated_at FROM jobs WHERE id='j1'").fetchone()[0] == "done"
    )
