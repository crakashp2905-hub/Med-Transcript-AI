"""Full-recording diarization against upstream turn labels, not clinical gold."""
import argparse
import itertools
import json
import time
from pathlib import Path

from services.diarization import diarize


def score_turns(reference, predicted):
    refs=sorted({r['role'] for r in reference})
    hyps=sorted({r['speaker_id'] for r in predicted if r.get('speaker_id') is not None})
    if len(refs)>4 or len(hyps)>100:
        raise ValueError('Development scorer assignment budget exceeded')
    boundaries=sorted({x[k] for x in reference+predicted for k in ('start_ms','end_ms')})
    intervals=[]
    intersections={(r,h):0 for r in refs for h in hyps}
    for a,b in zip(boundaries,boundaries[1:]):
        rs={r['role'] for r in reference if r['start_ms']<b and r['end_ms']>a}
        hs={r['speaker_id'] for r in predicted if r.get('speaker_id') is not None and r['start_ms']<b and r['end_ms']>a}
        intervals.append((b-a,rs,hs))
        for r in rs:
            for h in hs:
                intersections[r,h]+=b-a
    # One-to-one global optimal mapping; anonymous clusters never imply clinical roles.
    padded=hyps+[f'__missing_{i}' for i in range(max(0,len(refs)-len(hyps)))]
    assignment=max(itertools.permutations(padded,len(refs)),key=lambda hs:sum(
        intersections.get((r,h),0) for r,h in zip(refs,hs)),default=())
    mapping={h:r for r,h in zip(refs,assignment)}
    total=miss=false=confusion=0
    for ms,rs,hs in intervals:
        total+=len(rs)*ms
        miss+=max(0,len(rs)-len(hs))*ms
        false+=max(0,len(hs)-len(rs))*ms
        correct=sum(mapping.get(h) in rs for h in hs)
        confusion+=(min(len(rs),len(hs))-correct)*ms
    return {'reference_speaker_ms':total,'missed_speaker_ms':miss,'false_alarm_speaker_ms':false,
        'confused_speaker_ms':confusion,'diarization_error_rate':(miss+false+confusion)/total if total else None,
        'collar_ms':0,'overlap_scored':True,'optimal_scoring_mapping':mapping,
        'predicted_clusters':len(hyps),'reference_speakers':len(refs),
        'reference_status':'upstream_TextGrid_turn_labels_not_independently_adjudicated',
        'scoring_mapping_is_not_clinician_role_confirmation':True}


def run(manifest_path, model_path, output, threshold=None):
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    model=json.loads(Path(model_path).read_text(encoding='utf-8'))
    if threshold is not None:
        model['clustering_threshold']=threshold
    report={'dataset_id':manifest['dataset_id'],'data_class':'approved_public_mock',
        'model':model,'clinical_acceptance':False,'cases':[]}
    for case in manifest['cases']:
        audio=Path('data/datasets/primock57-full-v1')/case['audio']
        from services.api.ingest import file_sha256
        if file_sha256(audio)!=case['audio_sha256']:
            raise ValueError('Source audio hash mismatch')
        start=time.perf_counter()
        try:
            result=diarize(audio,model)
            row={'id':case['group_id'],'failed':False,'duration_ms':case['duration_ms'],
                'metrics':score_turns(case['reference_turns'],result['segments']),'result':result}
        except Exception as e:
            row={'id':case['group_id'],'failed':True,'error_type':type(e).__name__}
        row['wall_seconds']=time.perf_counter()-start
        report['cases'].append(row)
        Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k!='result'}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default='evaluation/datasets/primock57-full-v1/manifest.json')
    p.add_argument('--model',default='data/models/public-diarization-v1/manifest.json')
    p.add_argument('--output',default='evaluation/reports/public-diarization-2026-10-25.json')
    p.add_argument('--threshold',type=float)
    a=p.parse_args();run(a.manifest,a.model,a.output,a.threshold)
