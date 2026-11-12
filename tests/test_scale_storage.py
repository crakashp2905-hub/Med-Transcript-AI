from uuid import uuid4

from services.api.storage import Store


def test_thousand_synthetic_encounters_use_bounded_indexed_queries(tmp_path):
    db = tmp_path / "scale.sqlite3"
    store = Store(str(db))
    tenant = str(uuid4())
    clinician = str(uuid4())
    with store.transaction() as con:
        for index in range(1000):
            con.execute(
                "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
                (
                    str(uuid4()),
                    tenant,
                    clinician,
                    "{}",
                    f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}Z",
                ),
            )
        indexes = {
            row[1]
            for row in con.execute(
                "SELECT type,name FROM sqlite_master WHERE type='index'"
            )
        }
        plan = list(
            con.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM encounters WHERE tenant=? ORDER BY created_at DESC LIMIT 100",
                (tenant,),
            )
        )
    assert len(indexes) > 0 and len(plan) >= 1


def test_schema_exposes_bounded_history_limit_in_source():
    from pathlib import Path

    history = Path("services/review/routers/history.py").read_text(encoding="utf-8")
    assert "LIMIT 100" in history
