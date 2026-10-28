"""Prepare source-only reviewer and three-arm study packets; never invent observations."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil

from services.api.ingest import file_sha256
from services.annotation_workflow import packet


def prepare(manifest_path,audio_root,output):
    manifest_path=Path(manifest_path);manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    root=Path(output)
    if root.exists():raise ValueError('Use a new packet directory to preserve the review protocol')
    root.mkdir(parents=True);(root/'audio').mkdir()
    cases=list(manifest['cases']);random.Random(20261029).shuffle(cases)
    blinded=[];mapping=[]
    for index,case in enumerate(cases,1):
        ident=f'case-{index:03}';filename=f'{ident}.wav';source=Path(audio_root)/case['audio']
        if file_sha256(source)!=case['audio_sha256']:raise ValueError('Source changed')
        shutil.copyfile(source,root/'audio'/filename)
        blinded.append({'group_id':ident,'audio':filename,'audio_sha256':case['audio_sha256'],
            'duration_ms':case['duration_ms'],'reference_turns':case['reference_turns']})
        mapping.append({'blinded_id':ident,'source_id':case['group_id'],'foreground_id':case['foreground_id'],'condition':case['condition']})
    source={'dataset_id':manifest['dataset_id']+'-blinded-source-only','cases':blinded}
    for reviewer in ('A','B'):
        value=packet(source);value['instructions']='Independent complete-audio review; no ASR hypotheses, source summary notes or donor labels supplied. Upstream transcript is not adjudicated gold. Annotate uncertainty, medications/dose/unit/route/frequency/duration, allergy/reaction, negation, subject, timing, omissions and foreground/background attribution. Reviewer credentials and real listening must be independently verified.'
        (root/f'reviewer-{reviewer}.blank.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    (root/'operator-mapping.private.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8')
    clean=[m for m in mapping if m['condition']=='clean'];arms=['manual','deterministic','local_qwen']
    from itertools import permutations
    orders=list(permutations(arms))
    protocol={'schema_version':'three_arm_clinician_protocol_draft_v1','source_manifest_sha256':file_sha256(manifest_path),
        'purpose':'compare_note_accuracy_and_clinician_correction_time','approval_status':'not_approved','clinical_owner':None,
        'reviewer_qualifications_verified':False,'washout_and_training_plan':None,'arms':arms,
        'planned_pairs':[{'pair_id':f'pair-{i+1:03}','foreground_id':m['foreground_id'],'reviewer_id':None,'proposed_order':list(orders[i%len(orders)])} for i,m in enumerate(clean)],
        'required_observations':['wall_seconds','active_edit_seconds','independently_adjudicated_critical_errors','independently_adjudicated_omissions','provider_cost_usd','hardware_cost_usd'],
        'limitations':['Draft counterbalancing is not institutional study approval.','Repeated-case exposure needs a clinician-approved washout/training design.','Automatic model runtime is not clinician correction time.','Reference notes are not exhaustive atomic clinical gold.']}
    (root/'study-protocol.draft.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    observations={'schema_version':'three_arm_observations_v1','protocol_sha256':file_sha256(root/'study-protocol.draft.json'),
        'planned_pairs':[p['pair_id'] for p in protocol['planned_pairs']],'observations':[]}
    (root/'study-observations.blank.json').write_text(json.dumps(observations,indent=2)+'\n',encoding='utf-8')
    receipt={'schema_version':'detailed_review_packet_receipt_v1','source_manifest_sha256':file_sha256(manifest_path),
        'audio_files_verified':len(blinded),'reviewers_available':False,'annotations_complete':False,'clinician_observations':0,
        'planned_three_arm_pairs':len(clean),'model_outputs_in_reviewer_packets':False,'upstream_reference_notes_in_reviewer_packets':False,
        'physical_hardware_validated':False,'clinical_release_authorized':False,
        'packet_sha256':{p.name:file_sha256(p) for p in root.glob('*.json') if 'private' not in p.name}}
    return receipt


def summarize(document):
    pairs=document['planned_pairs'];arms=('manual','deterministic','local_qwen')
    if not pairs or len(pairs)!=len(set(pairs)):raise ValueError('Unique frozen pair roster required')
    if not isinstance(document['protocol_sha256'],str) or len(document['protocol_sha256'])!=64:raise ValueError('Frozen protocol hash required')
    int(document['protocol_sha256'],16)
    import math
    rows={}
    for row in document['observations']:
        key=(row['pair_id'],row['arm'])
        if key[0] not in pairs or key[1] not in arms or key in rows or row.get('status') not in ('complete','failed'):raise ValueError('Unknown/duplicate condition or missing status')
        if row['status']=='complete':
            for field in ('wall_seconds','active_edit_seconds'):
                v=row.get(field)
                if type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Observed finite timing required')
            if row['active_edit_seconds']>row['wall_seconds']:raise ValueError('Active time exceeds wall time')
            for field in ('independently_adjudicated_critical_errors','independently_adjudicated_omissions'):
                if type(row.get(field)) is not int or row[field]<0:raise ValueError('Independent integer error observations required')
        for field in ('provider_cost_usd','hardware_cost_usd'):
            v=row.get(field)
            if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<0):raise ValueError('Cost must be unknown or observed finite nonnegative')
        rows[key]=row
    from statistics import median
    comparisons={}
    for arm in arms[1:]:
        deltas=[]
        for pair in pairs:
            a,b=rows.get((pair,'manual')),rows.get((pair,arm))
            if a and b and a['status']==b['status']=='complete':deltas.append(a['wall_seconds']-b['wall_seconds'])
        comparisons[arm]={'complete_pairs':len(deltas),'incomplete_pairs':len(pairs)-len(deltas),'median_seconds_saved_complete_pairs_only':median(deltas) if deltas else None}
    return {'schema_version':'three_arm_study_summary_v1','planned_conditions':len(pairs)*3,'observed_conditions':len(rows),
        'missing_conditions':len(pairs)*3-len(rows),'failed_conditions':sum(r['status']=='failed' for r in rows.values()),
        'comparisons':comparisons,'cost_totals':{field:sum(r[field] for r in rows.values()) if rows and all(r.get(field) is not None for r in rows.values()) else None for field in ('provider_cost_usd','hardware_cost_usd')},'clinical_acceptance':False,'limitations':['Missing and failed conditions remain in counts.','Reviewer identity, independent adjudication and actual observations require human audit.','No causal productivity or clinical safety claim.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',default='evaluation/datasets/meddistract-detailed-v1/manifest.json');p.add_argument('--audio-root',default='data/datasets/meddistract-detailed-v1');p.add_argument('--output',default='data/human-review/meddistract-detailed-v1');p.add_argument('--receipt',default='evaluation/reports/detailed-review-preparation-2026-10-29.json');p.add_argument('--observations');p.add_argument('--protocol');a=p.parse_args()
    if a.observations:
        if not a.protocol:p.error('Observed study analysis requires its frozen protocol file')
        document=json.loads(Path(a.observations).read_text());protocol=json.loads(Path(a.protocol).read_text())
        if document['protocol_sha256']!=file_sha256(a.protocol) or document['planned_pairs']!=[r['pair_id'] for r in protocol['planned_pairs']]:raise ValueError('Observed study protocol or roster changed')
        r=summarize(document)
    else:r=prepare(a.manifest,a.audio_root,a.output)
    with Path(a.receipt).open('x',encoding='utf-8') as out:json.dump(r,out,indent=2);out.write('\n')
