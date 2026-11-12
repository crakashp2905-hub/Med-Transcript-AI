import json
import sqlite3
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from services.audit_integrity import verify, AuditIntegrityError
from services.api.storage import Store, MIGRATIONS
from tests.test_foundation import headers
from tests.test_review_workflow import prepare, draft, approve


@pytest.mark.parametrize(
    "attack", ["mutate_event", "remove_event", "reorder_chain", "remove_bootstrap"]
)
def test_local_audit_tampering_is_detected_and_prevents_approval(setup, attack):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    with Store(path).transaction() as con:
        assert verify(con)["events_verified"] > 0
    with sqlite3.connect(path) as con:
        if attack == "mutate_event":
            con.execute(
                "UPDATE audit SET action='tampered' WHERE id=(SELECT id FROM audit LIMIT 1)"
            )
        elif attack == "remove_event":
            con.execute("DELETE FROM audit WHERE id=(SELECT id FROM audit LIMIT 1)")
        elif attack == "reorder_chain":
            con.execute("UPDATE audit_chain SET seq=999999 WHERE seq=1")
        else:
            con.execute("DELETE FROM integrity_bootstrap")
    with Store(path).transaction() as con:
        with pytest.raises(AuditIntegrityError):
            verify(con)
    response = approve(client, eid, note)
    assert (
        response.status_code == 409
        and response.json()["code"] == "audit_integrity_failure"
    )


def test_approval_body_and_export_byte_tampering_are_rejected(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    approved = approve(client, eid, note).json()
    receipt = client.post(
        f"/v1/encounters/{eid}/exports",
        headers=headers(),
        json={"approval_id": approved["id"], "format": "json"},
    ).json()
    with sqlite3.connect(path) as con:
        con.execute(
            "UPDATE exports SET artifact='altered' WHERE id=?", (receipt["id"],)
        )
    assert client.get(receipt["download_url"], headers=headers()).status_code == 409
    with sqlite3.connect(path) as con:
        row = con.execute(
            "SELECT body FROM approvals WHERE id=?", (approved["id"],)
        ).fetchone()
        body = json.loads(row[0])
        body["patient_identifiers_reconfirmed"] = False
        con.execute(
            "UPDATE approvals SET body=? WHERE id=?", (json.dumps(body), approved["id"])
        )
    assert (
        client.get(f"/v1/encounters/{eid}/workspace", headers=headers()).status_code
        == 409
    )
    assert (
        client.post(
            f"/v1/encounters/{eid}/exports",
            headers=headers(),
            json={"approval_id": approved["id"], "format": "text"},
        ).status_code
        == 409
    )


def test_legacy_audit_backfill_is_repeatable_and_does_not_rewrite_history(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    event = (
        str(uuid4()),
        str(uuid4()),
        str(uuid4()),
        "legacy_event",
        "record",
        datetime.now(timezone.utc).isoformat(),
    )
    audit_index = next(
        i
        for i, migration in enumerate(MIGRATIONS)
        if "CREATE TABLE audit_chain" in migration
    )
    with sqlite3.connect(path) as con:
        for migration in MIGRATIONS[:audit_index]:
            con.executescript(migration)
        con.execute(f"PRAGMA user_version={audit_index}")
        con.execute("INSERT INTO audit VALUES (?,?,?,?,?,?)", event)
    Store(path)
    Store(path)
    with Store(path).transaction() as con:
        assert verify(con)["events_verified"] == 1
        assert tuple(con.execute("SELECT * FROM audit").fetchone()) == event
        assert (
            con.execute(
                "SELECT legacy_audit_count FROM integrity_bootstrap"
            ).fetchone()[0]
            == 1
        )


def test_exported_markdown_escapes_active_markup_but_json_preserves_text():
    from services.review.engine import escape_markdown

    text = "<script>alert(1)</script> ![pixel](https://outside.example/image)"
    escaped = escape_markdown(text)
    assert "<script>" not in escaped and "![" not in escaped
    assert "&lt;script&gt;" in escaped and "\\!" in escaped
