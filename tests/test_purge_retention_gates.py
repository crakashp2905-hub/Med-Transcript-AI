import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.api.storage import Store
from services.maintenance import purge


@pytest.mark.parametrize("hold_kind", ["legal_hold", "approval"])
def test_purge_preserves_assets_and_request_while_retention_gate_is_active(
    tmp_path, hold_kind
):
    database = str(tmp_path / "synthetic.sqlite3")
    assets = tmp_path / "assets"
    assets.mkdir()
    upload_id = str(uuid4())
    encounter_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    audio = assets / f"{upload_id}.wav"
    audio.write_bytes(b"synthetic-audio")

    with Store(database).transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at,legal_hold) VALUES (?,?,?,?,?,?)",
            (
                encounter_id,
                "synthetic-tenant",
                "synthetic-clinician",
                "{}",
                now,
                int(hold_kind == "legal_hold"),
            ),
        )
        con.execute(
            "INSERT INTO deletion_requests(id,encounter,status,created_at) VALUES (?,?,?,?)",
            (str(uuid4()), encounter_id, "pending", now),
        )
        if hold_kind == "approval":
            note_id = str(uuid4())
            con.execute(
                "INSERT INTO documents(id,encounter,kind,version,sha256,body,created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    note_id,
                    encounter_id,
                    "note",
                    1,
                    hashlib.sha256(b"note").hexdigest(),
                    "{}",
                    now,
                ),
            )
            con.execute(
                "INSERT INTO approvals(id,encounter,note,body,created_at) VALUES (?,?,?,?,?)",
                (str(uuid4()), encounter_id, note_id, "{}", now),
            )

    result = purge(database, str(assets))

    assert result["requests"][0]["status"] == "held_for_retention_review"
    assert audio.read_bytes() == b"synthetic-audio"
    with Store(database).transaction() as con:
        assert (
            con.execute(
                "SELECT status FROM deletion_requests WHERE encounter=?",
                (encounter_id,),
            ).fetchone()[0]
            == "pending"
        )
