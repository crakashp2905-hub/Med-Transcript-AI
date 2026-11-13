"""Explicit, fail-closed encounter lifecycle transitions."""

from enum import StrEnum
from datetime import datetime, timezone


class Stage(StrEnum):
    CREATED = "created"
    RECORDING = "recording"
    TRANSCRIBED = "transcribed"
    DRAFTED = "drafted"
    VERIFIED = "verified"
    APPROVED = "approved"
    REVOKED = "revoked"


ALLOWED = {
    Stage.CREATED: {Stage.RECORDING},
    Stage.RECORDING: {Stage.TRANSCRIBED},
    Stage.TRANSCRIBED: {Stage.TRANSCRIBED, Stage.DRAFTED},
    Stage.DRAFTED: {Stage.TRANSCRIBED, Stage.DRAFTED, Stage.VERIFIED},
    Stage.VERIFIED: {Stage.TRANSCRIBED, Stage.DRAFTED, Stage.APPROVED},
    Stage.APPROVED: {Stage.TRANSCRIBED, Stage.DRAFTED, Stage.REVOKED},
    Stage.REVOKED: set(),
}


def transition(
    current,
    target,
    *,
    tenant_id,
    expected_tenant_id,
    version,
    expected_version,
    revoked=False,
):
    if tenant_id != expected_tenant_id:
        raise ValueError("cross_tenant_transition")
    if revoked or current == Stage.REVOKED:
        raise ValueError("revoked_transition")
    if version != expected_version:
        raise ValueError("stale_transition")
    current, target = Stage(current), Stage(target)
    if target not in ALLOWED[current]:
        raise ValueError("illegal_or_double_transition")
    return {"stage": target, "version": version + 1}


def advance_persisted(con, encounter_id, target):
    """Advance a lifecycle row inside the caller's write transaction.

    The compare-and-swap update makes the helper's checks part of persistence,
    so an API path cannot commit an artifact without its matching state change.
    """
    encounter = con.execute(
        "SELECT tenant FROM encounters WHERE id=?", (str(encounter_id),)
    ).fetchone()
    if encounter is None:
        raise ValueError("encounter_not_found")
    row = con.execute(
        "SELECT stage,version FROM encounter_lifecycle WHERE encounter=?",
        (str(encounter_id),),
    ).fetchone()
    if row is None:
        raise ValueError("encounter_lifecycle_missing")
    result = transition(
        row["stage"],
        target,
        tenant_id=encounter["tenant"],
        expected_tenant_id=encounter["tenant"],
        version=row["version"],
        expected_version=row["version"],
    )
    changed = con.execute(
        "UPDATE encounter_lifecycle SET stage=?,version=?,updated_at=? "
        "WHERE encounter=? AND stage=? AND version=?",
        (
            result["stage"].value,
            result["version"],
            datetime.now(timezone.utc).isoformat(),
            str(encounter_id),
            row["stage"],
            row["version"],
        ),
    ).rowcount
    if changed != 1:
        raise ValueError("stale_transition")
    return result
