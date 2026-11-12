import json
import sqlite3
from uuid import uuid4
import pytest
from services.api.storage import Store, MIGRATIONS
from services.canonical import content_sha256
from services.domain_contracts import validate_record
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare, draft


@pytest.mark.parametrize("kind", ["draft_proposal", "fact_proposal"])
def test_changed_persisted_proposals_are_rejected_before_display(setup, kind):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    endpoint = "draft-proposals" if kind == "draft_proposal" else "fact-proposals"
    response = client.post(
        f"/v1/encounters/{eid}/{endpoint}",
        headers=headers(),
        json={
            "transcript_version_id": tx["id"],
            **({"facts": facts} if kind == "draft_proposal" else {}),
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    read_endpoint = (
        "draft-proposals" if kind == "draft_proposal" else "clinical-proposals"
    )
    route = f"/v1/encounters/{eid}/{read_endpoint}/{result['id']}"
    assert client.get(route, headers=headers()).status_code == 200
    with sqlite3.connect(path) as con:
        con.execute("DROP TRIGGER model_proposals_immutable")
        changed = dict(result)
        changed["transcript_sha256"] = "0" * 64
        con.execute(
            "UPDATE model_proposals SET body=? WHERE id=?",
            (json.dumps(changed), result["id"]),
        )
    assert client.get(route, headers=headers()).status_code == 409


def test_rehashed_proposal_cannot_borrow_another_encounters_source(setup):
    client, path, _ = setup
    eid, tx, _ = prepare(client, path)
    _, other, _ = prepare(client, path)
    proposal = client.post(
        f"/v1/encounters/{eid}/fact-proposals",
        headers=headers(),
        json={"transcript_version_id": tx["id"]},
    ).json()
    proposal.update(
        transcript_version_id=other["id"], transcript_sha256=other["sha256"]
    )
    with sqlite3.connect(path) as con:
        con.execute("DROP TRIGGER model_proposals_immutable")
        con.execute(
            "UPDATE model_proposals SET body=?,sha256=? WHERE id=?",
            (json.dumps(proposal), content_sha256(proposal), proposal["id"]),
        )
    assert (
        client.get(
            f"/v1/encounters/{eid}/clinical-proposals/{proposal['id']}",
            headers=headers(),
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "attack", ["mutate_metric", "remove_metric", "remove_seal", "mutate_session"]
)
def test_review_timing_tampering_is_not_reported_as_an_observed_completion(
    setup, attack
):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    base = f"/v1/encounters/{eid}/review-sessions"
    session = client.post(
        base, headers=headers(), json={"note_version_id": note["id"]}
    ).json()
    completion = client.post(
        base + "/" + session["id"] + "/complete",
        headers=headers(),
        json={"note_version_id": note["id"]},
    )
    assert completion.status_code == 200
    with sqlite3.connect(path) as con:
        if attack == "mutate_metric":
            body = completion.json()
            body["word_edits"] += 1
            con.execute("DROP TRIGGER review_metrics_immutable")
            con.execute(
                "UPDATE review_metrics SET body=? WHERE session=?",
                (json.dumps(body), session["id"]),
            )
        elif attack == "remove_metric":
            con.execute("DELETE FROM review_metrics WHERE session=?", (session["id"],))
        elif attack == "remove_seal":
            con.execute(
                "DELETE FROM review_metric_integrity WHERE session=?", (session["id"],)
            )
        else:
            con.execute("DROP TRIGGER model_proposals_immutable")
            body = dict(session)
            body["started_at"] = "2000-01-01T00:00:00+00:00"
            con.execute(
                "UPDATE model_proposals SET body=? WHERE id=?",
                (json.dumps(body), session["id"]),
            )
    assert client.get(base, headers=headers()).status_code == 409
    assert (
        client.post(
            base + "/" + session["id"] + "/complete",
            headers=headers(),
            json={"note_version_id": note["id"]},
        ).status_code
        == 409
    )


def test_legacy_metric_seals_are_one_time_snapshots_without_rewriting_bodies(setup):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path)
    note = draft(client, eid, tx, facts)["note"]
    base = f"/v1/encounters/{eid}/review-sessions"
    session = client.post(
        base, headers=headers(), json={"note_version_id": note["id"]}
    ).json()
    assert (
        client.post(
            base + "/" + session["id"] + "/complete",
            headers=headers(),
            json={"note_version_id": note["id"]},
        ).status_code
        == 200
    )
    with sqlite3.connect(path) as con:
        before = con.execute("SELECT body FROM review_metrics").fetchone()[0]
        con.execute("DROP TABLE review_metric_integrity")
        seal_version = next(
            i
            for i, sql in enumerate(MIGRATIONS, 1)
            if "CREATE TABLE review_metric_integrity" in sql
        )
        con.execute(f"PRAGMA user_version={seal_version - 1}")
    # Replay only the migration under test; later migrations already exist.
    from unittest.mock import patch

    with patch("services.api.storage.MIGRATIONS", MIGRATIONS[:seal_version]):
        Store(path)
        Store(path)
    with sqlite3.connect(path) as con:
        con.execute(f"PRAGMA user_version={len(MIGRATIONS)}")
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT body FROM review_metrics").fetchone()[0] == before
        assert (
            con.execute("SELECT origin FROM review_metric_integrity").fetchone()[0]
            == "legacy_snapshot_not_external_attestation"
        )
    assert client.get(base, headers=headers()).status_code == 200


@pytest.mark.parametrize(
    "body", [[], None, "clinical source must not appear in errors", 42]
)
def test_nonobject_persisted_proposals_fail_with_safe_codes(body):
    with pytest.raises(ValueError, match="persisted_record_object_required"):
        validate_record("fact_proposal", body)
