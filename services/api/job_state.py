"""Scoped callers use this for nonclinical progress and retry metadata."""
import json


def retryable(row):
    return row['stage']=='transcription' and row['status']=='failed' and row['attempts']<3 and row['error_code'] in {'asr_failed','worker_lease_lost','asset_unavailable'}


def progress(con,row):
    if row['stage']!='transcription':return None
    ingest=con.execute("SELECT result FROM jobs WHERE upload=? AND stage='audio_ingest' AND status='succeeded'",(row['upload'],)).fetchone()
    metadata=json.loads(ingest['result']) if ingest else {}
    completed=con.execute('SELECT COUNT(*) FROM asr_checkpoints WHERE job=?',(row['id'],)).fetchone()[0]
    return {'completed_channels':completed,'total_channels':metadata.get('asr_channels',metadata.get('channels',0)),
            'partial_output_is_not_a_source_version':True}
