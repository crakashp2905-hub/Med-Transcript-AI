"""Independent scoring code against upstream labels; not independent human gold."""
import argparse
import json
from pathlib import Path
from services.api.ingest import file_sha256
from services.diarization_evaluation import score_turns


def boundaries(reference,predicted,tolerance=250):
    a,b=sorted(reference),sorted(predicted)
    i=j=hits=0
    while i<len(a) and j<len(b):
        if abs(a[i]-b[j])<=tolerance:hits+=1;i+=1;j+=1
        elif a[i]<b[j]:i+=1
        else:j+=1
    return {'reference_boundaries':len(a),'predicted_boundaries':len(b),'matched':hits,
            'missed':len(a)-hits,'extra':len(b)-hits,'tolerance_ms':tolerance,
            'f1':2*hits/(len(a)+len(b)) if a or b else None}


def role_metrics(reference,predicted,mapping):
    points=sorted({x[k] for x in reference+predicted for k in ('start_ms','end_ms')})
    roles=sorted({r['role'] for r in reference})
    result={role:{'reference_ms':0,'predicted_ms':0,'correct_ms':0,'missed_ms':0,'extra_ms':0} for role in roles}
    for a,b in zip(points,points[1:]):
        refs={r['role'] for r in reference if r['start_ms']<b and r['end_ms']>a}
        hyps={mapping.get(r['speaker_id'],'unassigned') for r in predicted if r['start_ms']<b and r['end_ms']>a}
        for role in roles:
            result[role]['reference_ms']+=(b-a)*(role in refs)
            result[role]['predicted_ms']+=(b-a)*(role in hyps)
            result[role]['correct_ms']+=(b-a)*(role in refs and role in hyps)
            result[role]['missed_ms']+=(b-a)*(role in refs and role not in hyps)
            result[role]['extra_ms']+=(b-a)*(role not in refs and role in hyps)
    for role in roles:
        row=result[role]
        row['recall']=row['correct_ms']/row['reference_ms'] if row['reference_ms'] else None
        row['precision']=row['correct_ms']/row['predicted_ms'] if row['predicted_ms'] else None
        row['boundaries']=boundaries([r[k] for r in reference if r['role']==role for k in ('start_ms','end_ms')],
            [r[k] for r in predicted if mapping.get(r['speaker_id'])==role for k in ('start_ms','end_ms')])
    return result


def compare(root,output):
    root=Path(root)
    manifest_path=root/'evaluation/datasets/primock57-full-v1/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if file_sha256(manifest_path)!=json.loads((manifest_path.parent/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen source changed')
    reference={r['group_id']:r for r in manifest['cases']}
    report={'schema_version':'speaker_comparison_v1','reference_status':'upstream_not_independently_adjudicated',
            'role_mapping':'optimal_reference_mapping_for_scoring_only_never_application_role_assignment',
            'clinical_acceptance':False,'conditions':[]}
    for label,filename in [('fixed_window','public-diarization-2026-10-25.json'),('separate_channels','two-channel-diarization-2026-10-26.json')]:
        path=root/'evaluation/reports'/filename;data=json.loads(path.read_text())
        if len(data['cases'])!=len(reference) or {r['id'] for r in data['cases']}!=set(reference):
            raise ValueError('All consultations required exactly once')
        rows=[]
        for case in data['cases']:
            segments=[] if case['failed'] else case.get('result',{}).get('segments',case.get('segments',[]))
            gold=reference[case['id']]['reference_turns'];metrics=score_turns(gold,segments)
            rows.append({'id':case['id'],'failed':case['failed'],'metrics':metrics,
                         'role_errors':role_metrics(gold,segments,metrics['optimal_scoring_mapping'])})
        errors=sum(sum(c['metrics'][k] for k in ('missed_speaker_ms','false_alarm_speaker_ms','confused_speaker_ms')) for c in rows)
        total=sum(c['metrics']['reference_speaker_ms'] for c in rows)
        report['conditions'].append({'id':label,'evidence_sha256':file_sha256(path),'cases':rows,'weighted_der':errors/total})
    report['absolute_der_reduction']=report['conditions'][0]['weighted_der']-report['conditions'][1]['weighted_der']
    with Path(output).open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.')
    p.add_argument('--out',required=True);a=p.parse_args();compare(a.root,a.out)
