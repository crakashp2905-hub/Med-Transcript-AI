"""Post-hoc empty-output adapter reconstruction; never replaces original failures."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
from services.conversation_experiment import join_text,term_counts
from services.evaluation import score


def reconstruct(experiment,probe_path,output):
    body=Path(experiment).read_bytes();original=json.loads(body)
    probe_body=Path(probe_path).read_bytes();probe=json.loads(probe_body)
    if not original['complete'] or not probe['complete'] or probe['experiment_sha256']!=hashlib.sha256(body).hexdigest() or probe['model']!=original['model']:
        raise ValueError('Complete hash-bound matching probe evidence required')
    key=lambda mode,cid,role,c:(mode,cid,role,c['input_start_ms'],c['input_end_ms'])
    proofs={key(p['mode'],p['id'],p['role'],p):p for p in probe['probes']}
    if len(proofs)!=len(probe['probes']):raise ValueError('Duplicate probe evidence')
    rows=[]
    for source in original['runs']:
        if source['mode']!='two_channel':continue
        row=deepcopy(source);row['mode']='two_channel_allow_native_empty_v2';row['hypothesis']=''
        row['original_case_failed']=source['failed'];row['admitted_empty_native_outputs']=0
        for chunk in row['chunks']:
            if chunk['failed']:
                proof=proofs.get(key(source['mode'],source['id'],source['role'],chunk))
                if proof and proof.get('reproduced_failure') is True and proof.get('failure_kind')=='wrapper_rejects_empty_native_output':
                    chunk.update(failed=False,hypothesis='',native_empty_output=True,original_wrapper_failure_preserved_in_source=True)
                    row['admitted_empty_native_outputs']+=1
            row['hypothesis'],_=join_text(row['hypothesis'],chunk['hypothesis'],True)
        row['failed']=any(c['failed'] for c in row['chunks'])
        scored='' if row['failed'] else row['hypothesis']
        row.update(score(row['reference'],scored),clinical_terms=term_counts(row['reference'],scored))
        row['normalized_wer']=row['normalized_edits']/row['reference_words']
        rows.append(row)
    if not rows:raise ValueError('No separate-channel cases')
    words,edits=sum(r['reference_words'] for r in rows),sum(r['normalized_edits'] for r in rows)
    report={'schema_version':'native_empty_reconstruction_v1','experiment_sha256':hashlib.sha256(body).hexdigest(),
            'probe_sha256':hashlib.sha256(probe_body).hexdigest(),'model':original['model'],
            'manifest_sha256':original['manifest_sha256'],'runs':rows,'complete':True,
            'summary':{'reference_words':words,'normalized_edits':edits,'normalized_wer':edits/words,
                       'failed_runs':sum(r['failed'] for r in rows),'admitted_empty_native_outputs':sum(r['admitted_empty_native_outputs'] for r in rows)},
            'original_failures_preserved':True,'qualified_asr_candidate':False,'output_timestamp_support':False,
            'clinical_acceptance':False,'maximum_normalized_wer':.05,
            'method':'Reuse unchanged successful chunk hypotheses; reproduce every failed chunk; only explicitly empty native string results become empty hypotheses under the opt-in v2 adapter.',
            'limitations':['Post-hoc runtime reconstruction, not a fresh full inference run or independent acceptance result.',
                          'Empty hypotheses can omit actual speech; every reference word stays in the scoring denominator.',
                          'Other native failures remain failures and make the whole case score as empty.',
                          'Reported wall times belong to the original run and are not v2 latency evidence.',
                          'Input window bounds are not ASR timestamps; no application promotion.']}
    with Path(output).open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',required=True)
    p.add_argument('--probe',required=True);p.add_argument('--out',required=True);a=p.parse_args();reconstruct(a.experiment,a.probe,a.out)
