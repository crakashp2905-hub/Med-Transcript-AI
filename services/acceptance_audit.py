"""Audit reserved public source pointers without running models or generating gold."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request


def audit(root,output,fetch=True):
    root=Path(root)
    reservation_path=root/'evaluation/acceptance-reservation-v1.json'
    reservation=json.loads(reservation_path.read_text())
    reserved=set(reservation['reserved_groups']);used=set()
    for path in (root/'evaluation/datasets').glob('*/manifest.json'):
        manifest=json.loads(path.read_text(encoding='utf-8'))
        used.update(r['group_id'] for r in manifest.get('samples',[]))
        used.update(r['group_id'] for r in manifest.get('cases',[]))
    if reserved & used:raise ValueError('Acceptance/development group leakage')
    rows=[]
    if fetch:
        for group in reservation['reserved_groups']:
            for role in ('doctor','patient'):
                base=f'https://raw.githubusercontent.com/babylonhealth/primock57/{reservation["source_revision"]}'
                request=urllib.request.Request(f'{base}/audio/{group}_{role}.wav')
                with urllib.request.urlopen(request,timeout=30) as response:body=response.read(1001)
                if len(body)>1000:raise ValueError('Unexpected non-pointer source')
                pointer=body.decode()
                match=re.fullmatch(r'version https://git-lfs.github.com/spec/v1\s+oid sha256:([a-f0-9]{64})\s+size (\d+)\s*',pointer)
                if not match:raise ValueError('Invalid source LFS pointer')
                rows.append({'group_id':group,'role':role,'original_audio_sha256':match[1],
                             'original_audio_bytes':int(match[2]),'pointer_sha256':hashlib.sha256(body).hexdigest(),
                             'source_url':request.full_url,'audio_bytes_downloaded':False})
    result={'schema_version':'acceptance_source_audit_v1','reservation_sha256':hashlib.sha256(reservation_path.read_bytes()).hexdigest(),
            'reserved_groups':reservation['reserved_groups'],'development_groups':sorted(used),
            'group_disjoint':True,'sources':rows,'pointer_audit_complete':len(rows)==6,
            'audio_content_verified':False,'speaker_independence_verified':False,
            'human_qualifications_verified':False,'adjudicated':False,'acceptance_authorized':False}
    with Path(output).open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.')
    p.add_argument('--out',required=True);a=p.parse_args();audit(a.root,a.out)
