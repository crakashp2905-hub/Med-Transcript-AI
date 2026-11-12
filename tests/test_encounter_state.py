import sqlite3
import pytest
from uuid import uuid4

from services.encounter_state import Stage, transition
from services.encounter_state import advance_persisted
from services.api.storage import Store


def test_encounter_state_accepts_only_ordered_transition():
    result = transition(
        Stage.CREATED,
        Stage.RECORDING,
        tenant_id="a",
        expected_tenant_id="a",
        version=0,
        expected_version=0,
    )
    assert result == {"stage": Stage.RECORDING, "version": 1}


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"tenant_id": "b", "expected_tenant_id": "a"}, "cross_tenant_transition"),
        (
            {
                "tenant_id": "a",
                "expected_tenant_id": "a",
                "version": 1,
                "expected_version": 0,
            },
            "stale_transition",
        ),
        (
            {
                "tenant_id": "a",
                "expected_tenant_id": "a",
                "version": 0,
                "expected_version": 0,
                "revoked": True,
            },
            "revoked_transition",
        ),
    ],
)
def test_encounter_state_rejects_unsafe_transition(kwargs, error):
    base = {
        "version": 0,
        "expected_version": 0,
        "tenant_id": "a",
        "expected_tenant_id": "a",
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=error):
        transition(Stage.CREATED, Stage.RECORDING, **base)


def test_encounter_state_is_persisted_and_illegal_transition_rolls_back(tmp_path):
    database = Store(str(tmp_path / "lifecycle.sqlite3"))
    encounter_id = str(uuid4())
    with database.transaction() as con:
        con.execute(
            "INSERT INTO encounters(id,tenant,clinician,body,created_at) VALUES(?,?,?,?,?)",
            (encounter_id, "tenant-a", "clinician-a", "{}", "2026-11-12T00:00:00Z"),
        )
        con.execute(
            "INSERT INTO encounter_lifecycle(encounter,stage,version,updated_at) VALUES(?,?,?,?)",
            (encounter_id, Stage.CREATED.value, 0, "2026-11-12T00:00:00Z"),
        )
        assert advance_persisted(con, encounter_id, Stage.RECORDING) == {
            "stage": Stage.RECORDING,
            "version": 1,
        }
    with pytest.raises(ValueError, match="illegal_or_double_transition"):
        with database.transaction() as con:
            advance_persisted(con, encounter_id, Stage.APPROVED)
    with database.transaction() as con:
        row = con.execute(
            "SELECT stage,version FROM encounter_lifecycle WHERE encounter=?",
            (encounter_id,),
        ).fetchone()
    assert (row["stage"], row["version"]) == (Stage.RECORDING.value, 1)
    with pytest.raises(
        sqlite3.IntegrityError, match="Invalid encounter lifecycle version"
    ):
        with database.transaction() as con:
            con.execute(
                "UPDATE encounter_lifecycle SET stage='approved',version=2 WHERE encounter=?",
                (encounter_id,),
            )
