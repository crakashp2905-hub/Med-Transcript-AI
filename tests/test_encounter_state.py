import pytest

from services.encounter_state import Stage, transition


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
