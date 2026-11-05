"""Hash, schema and encounter/source binding checks for persisted proposals."""
from fastapi import HTTPException
from services.api.record_integrity import decode_record


def decode_proposal(con,row,eid):
    if row['encounter']!=str(eid):
        raise HTTPException(409,'persisted_artifact_integrity_failure')
    body=decode_record(row,row['kind'])
    note_id=body.get('note_version_id')
    if note_id:
        note=con.execute("SELECT id FROM documents WHERE id=? AND encounter=? AND kind='note'",(note_id,str(eid))).fetchone()
        if note is None:raise HTTPException(409,'persisted_artifact_integrity_failure')
    if row['kind']!='review_session':
        source=con.execute('SELECT sha256 FROM transcript_versions WHERE id=? AND encounter=?',(body['transcript_version_id'],str(eid))).fetchone()
        if source is None or source['sha256']!=body['transcript_sha256']:
            raise HTTPException(409,'persisted_artifact_integrity_failure')
    return body
