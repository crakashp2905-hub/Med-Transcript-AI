"""Prepare source-audited blank human packets; never runs inference or invents reviewers."""
import argparse
import hashlib
import json
from pathlib import Path
from services.api.ingest import file_sha256
from services.annotation_workflow import packet


def prepare(source,output):
    source,output=Path(source),Path(output)
    if output.exists():raise ValueError('Preserve existing human review materials')
    reservation_path=Path('evaluation/acceptance-reservation-v1.json');reservation=json.loads(reservation_path.read_text())
    manifest_path=source/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('split')!='reserved_human_annotation_only_no_inference' or set(c['group_id'] for c in manifest['cases'])!=set(reservation['reserved_groups']):
        raise ValueError('Exact reserved human-only cohort required')
    rows=[]
    for case in manifest['cases']:
        mixed=source/case['audio']
        if file_sha256(mixed)!=case['audio_sha256']:raise ValueError('Mixed source changed')
        for track in case['sources']:
            original=source/f"{case['group_id']}_{track['role']}.original.wav"
            normalized=source/track['normalized_audio'];grid=source/f"{case['group_id']}_{track['role']}.TextGrid"
            if file_sha256(original)!=track['original_sha256'] or file_sha256(normalized)!=track['normalized_sha256'] or file_sha256(grid)!=track['annotation_sha256']:
                raise ValueError('Source audio or upstream annotation changed')
            rows.append({'group_id':case['group_id'],'role':track['role'],'original_audio_sha256':file_sha256(original),
                'original_audio_bytes':original.stat().st_size,'normalized_audio_sha256':file_sha256(normalized),
                'annotation_sha256':file_sha256(grid)})
    output.mkdir(parents=True)
    for name in ('manifest.json','LICENSE.md','ATTRIBUTION.txt'):(output/name).write_bytes((source/name).read_bytes())
    lock={'manifest_sha256':file_sha256(manifest_path),'role':'reserved_human_annotation_only_no_inference',
          'reservation_sha256':file_sha256(reservation_path)}
    (output/'lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    blank=packet(manifest)
    for label in ('A','B'):(output/f'reviewer-{label}.blank.json').write_text(json.dumps(blank,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output/'qualification-registry.blank.json').write_text(json.dumps({'required_fields':reservation['qualification_registry_fields'],'reviewers':[],
        'credential_audit_complete':False,'institution':None,'deployment_country':None},indent=2)+'\n')
    result={'schema_version':'acceptance_human_materials_v1','manifest_sha256':file_sha256(manifest_path),
        'reservation_sha256':file_sha256(reservation_path),'audio_content_hash_verified':True,'sources':rows,
        'models_run_by_this_tool':False,'independent_audio_listening_complete':False,'qualified_reviewers_verified':False,
        'adjudicated':False,'clinical_gold':False,'clinical_release_authorized':False,
        'next_steps':['Qualified reviewers audit and correct upstream references against all audio before freezing the annotation source.',
                      'Two distinct reviewers independently annotate; a third resolves every disagreement.',
                      'The institution verifies credentials, site/speaker/device independence, protocol and approval privately.']}
    (output/'source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=prepare(a.source,a.output);print(json.dumps({'audio_content_hash_verified':r['audio_content_hash_verified'],'clinical_gold':False}))
