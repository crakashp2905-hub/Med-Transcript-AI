"""Explicit, fail-closed encounter lifecycle transitions."""

from enum import StrEnum


class Stage(StrEnum):
    CREATED = 'created'
    RECORDING = 'recording'
    TRANSCRIBED = 'transcribed'
    DRAFTED = 'drafted'
    VERIFIED = 'verified'
    APPROVED = 'approved'
    REVOKED = 'revoked'


ALLOWED = {
    Stage.CREATED: {Stage.RECORDING},
    Stage.RECORDING: {Stage.TRANSCRIBED},
    Stage.TRANSCRIBED: {Stage.DRAFTED},
    Stage.DRAFTED: {Stage.VERIFIED},
    Stage.VERIFIED: {Stage.APPROVED},
    Stage.APPROVED: set(),
    Stage.REVOKED: set(),
}


def transition(current, target, *, tenant_id, expected_tenant_id, version, expected_version, revoked=False):
    if tenant_id != expected_tenant_id:
        raise ValueError('cross_tenant_transition')
    if revoked or current == Stage.REVOKED:
        raise ValueError('revoked_transition')
    if version != expected_version:
        raise ValueError('stale_transition')
    current, target = Stage(current), Stage(target)
    if target not in ALLOWED[current]:
        raise ValueError('illegal_or_double_transition')
    return {'stage': target, 'version': version + 1}
