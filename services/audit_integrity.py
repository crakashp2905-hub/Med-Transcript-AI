"""Local tamper-evident audit/approval seals. No external immutability claim."""
from datetime import datetime, timezone
from fastapi import HTTPException
from services.canonical import content_sha256
from services.strict_json import loads

ZERO = '0'*64


class AuditIntegrityError(HTTPException):
    def __init__(self):
        super().__init__(409, 'audit_integrity_failure')


def event_hash(row):
    return content_sha256({key: row[key] for key in ('id', 'tenant', 'actor', 'action', 'resource', 'time')})


def chain_hash(seq, event_id, previous, event):
    return content_sha256({'seq': seq, 'event_id': event_id, 'previous_sha256': previous, 'event_sha256': event})


def initialize(con):
    """One-time data migration: append seals; never rewrite historical bodies."""
    previous = ZERO
    rows = con.execute('SELECT * FROM audit ORDER BY time,id').fetchall()
    for seq, row in enumerate(rows, 1):
        event = event_hash(row)
        current = chain_hash(seq, row['id'], previous, event)
        con.execute('INSERT INTO audit_chain VALUES (?,?,?,?,?)', (seq, row['id'], previous, event, current))
        previous = current
    stamp = datetime.now(timezone.utc).isoformat()
    approvals = con.execute('SELECT * FROM approvals').fetchall()
    for row in approvals:
        con.execute('INSERT INTO approval_integrity VALUES (?,?,?,?)',
                    (row['id'], content_sha256(loads(row['body'])), stamp, 'legacy_snapshot_not_external_attestation'))
    con.execute('INSERT INTO integrity_bootstrap VALUES (?,?,?,?,?)', (1, stamp, len(rows), len(approvals), previous))


def verify(con):
    if con.execute('SELECT id FROM integrity_bootstrap WHERE id=1').fetchone() is None:
        raise AuditIntegrityError()
    rows = con.execute('SELECT * FROM audit_chain ORDER BY seq').fetchall()
    events = {row['id']: row for row in con.execute('SELECT * FROM audit').fetchall()}
    if len(rows) != len(events):
        raise AuditIntegrityError()
    previous = ZERO
    for seq, row in enumerate(rows, 1):
        event = events.get(row['event_id'])
        if (event is None or row['seq'] != seq or row['previous_sha256'] != previous
                or row['event_sha256'] != event_hash(event)
                or row['chain_sha256'] != chain_hash(seq, row['event_id'], previous, row['event_sha256'])):
            raise AuditIntegrityError()
        previous = row['chain_sha256']
    return {'events_verified': len(rows), 'tail_sha256': previous, 'external_immutability': False}


def append(con, event):
    from services.domain_contracts import validate_record
    value = dict(zip(('id', 'tenant', 'actor', 'action', 'resource', 'time'), event))
    validate_record('audit', value)
    if con.execute('SELECT id FROM integrity_bootstrap WHERE id=1').fetchone() is None:
        raise AuditIntegrityError()
    tip = con.execute('SELECT * FROM audit_chain ORDER BY seq DESC LIMIT 1').fetchone()
    seq, previous = (tip['seq']+1, tip['chain_sha256']) if tip else (1, ZERO)
    if tip:
        prior = con.execute('SELECT * FROM audit WHERE id=?', (tip['event_id'],)).fetchone()
        if prior is None or tip['event_sha256'] != event_hash(prior):
            raise AuditIntegrityError()
    digest = event_hash(value)
    con.execute('INSERT INTO audit VALUES (?,?,?,?,?,?)', event)
    con.execute('INSERT INTO audit_chain VALUES (?,?,?,?,?)', (seq, value['id'], previous, digest, chain_hash(seq, value['id'], previous, digest)))


def seal_approval(con, approval_id, body, stamp):
    from services.domain_contracts import validate_record
    validate_record('approval', body)
    con.execute('INSERT INTO approval_integrity VALUES (?,?,?,?)', (approval_id, content_sha256(body), stamp, 'created_with_current_approval'))


def approval_body(con, row):
    from services.domain_contracts import validate_record
    try:
        verify(con)
        body = loads(row['body'])
        validate_record('approval', body)
        seal = con.execute('SELECT sha256 FROM approval_integrity WHERE approval_id=?', (row['id'],)).fetchone()
        if (seal is None or seal['sha256'] != content_sha256(body) or body['id'] != row['id']
                or body['note_version_id'] != row['note'] or body['approved_at'] != row['created_at']):
            raise ValueError('approval_seal_mismatch')
        attestation = con.execute("SELECT id FROM audit WHERE action='exact_version_approved' AND resource=? AND actor=?",
                                  (row['id'], body['clinician_id'])).fetchone()
        if attestation is None:
            raise ValueError('approval_audit_missing')
        return body
    except (ValueError, KeyError, TypeError):
        raise AuditIntegrityError() from None
