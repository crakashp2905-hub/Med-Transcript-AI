"""Hash-bound post-hoc full-case reconstruction; original failures remain immutable."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from services.evaluation import score,wer_gate


def reconstruct(experiment,probe_path,output):
    out=Path(output)
    if out.exists():raise ValueError('Preserve original evidence')
    raw=Path(experiment).read_bytes();original=json.loads(raw)
    proof_raw=Path(probe_path).read_bytes();proof=json.loads(proof_raw)
    if not original['complete'] or not proof['complete'] or proof['experiment_sha256']!=hashlib.sha256(raw).hexdigest() or proof['model']!=original['model']:
        raise ValueError('Complete matching hash-bound proof required')
    keys=lambda row:(row['id'],row['input_start_ms'],row['input_end_ms'])
    proofs={keys(p):p for p in proof['probes']}
    if len(proofs)!=len(proof['probes']):raise ValueError('Duplicate proof')
    rows=[]
    for source in original['cases']:
        row=deepcopy(source);row['original_case_failed']=source['failed'];row['admitted_native_empty_outputs']=0
        for chunk in row['chunks']:
            if chunk['failed']:
                evidence=proofs.get((row['id'],chunk['start_ms'],chunk['end_ms']))
                if evidence and evidence.get('reproduced_failure') and evidence.get('failure_kind')=='wrapper_rejects_empty_native_output':
                    chunk.update(failed=False,hypothesis='',native_empty_output=True);row['admitted_native_empty_outputs']+=1
        row['failed']=any(c['failed'] for c in row['chunks'])
        row['hypothesis']='' if row['failed'] else ' '.join(c['hypothesis'] for c in row['chunks'])
        row.update(score(row['reference'],row['hypothesis']));rows.append(row)
    words=sum(r['reference_words'] for r in rows);edits=sum(r['normalized_edits'] for r in rows)
    summary={'reference_words':words,'normalized_edits':edits,'normalized_wer':edits/words,'failed_samples':sum(r['failed'] for r in rows)}
    report={'schema_version':'full_native_empty_reconstruction_v1','experiment_sha256':hashlib.sha256(raw).hexdigest(),
        'probe_sha256':hashlib.sha256(proof_raw).hexdigest(),'manifest_sha256':original['manifest_sha256'],'model':original['model'],
        'cases':rows,'summary':summary,'wer_gate':wer_gate(summary,.05),'complete':True,'clinical_acceptance':False,
        'original_failures_preserved':True,'output_timestamp_support':False,'qualified_asr_candidate':False,
        'limitations':['Post-hoc reuse of successful outputs, not a fresh or independent acceptance run.','Only freshly reproduced exact native-empty failures become empty predictions.','Every reference word remains scored; other failures score the whole case empty.','Wall times are from the original run and cannot measure this reconstruction.','Chunk bounds are not model timestamps.']}
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',required=True);p.add_argument('--probe',required=True);p.add_argument('--out',required=True);a=p.parse_args();reconstruct(a.experiment,a.probe,a.out)
