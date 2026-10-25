"""Check publication artifact bytes; this never authorizes clinical release."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root,index,check_current_source=False):
    root=Path(root).resolve()
    def path(name):
        value=(root/name).resolve()
        if not value.is_relative_to(root) or not value.is_file():raise ValueError('Invalid evidence path')
        return value
    document=json.loads(path(index).read_text(encoding='utf-8'))
    if document['schema_version']!='scribe_evidence_index_v2':raise ValueError('Unsupported evidence index')
    for name,expected in document['artifact_sha256'].items():
        if hashlib.sha256(path(name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Artifact integrity failure: '+name)
    if check_current_source:
        for name,expected in document['source_text_sha256'].items():
            text=path(name).read_text(encoding='utf-8')
            if hashlib.sha256(text.encode('utf-8')).hexdigest()!=expected:
                raise ValueError('Current source differs from publication snapshot: '+name)
    return {'artifact_files_verified':len(document['artifact_sha256']),
            'current_source_checked':check_current_source,'clinical_release_authorized':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.')
    p.add_argument('--index',default='evaluation/reports/scribe-evidence-index-2026-10-26.json')
    p.add_argument('--check-current-source',action='store_true');a=p.parse_args()
    print(json.dumps(verify(a.root,a.index,a.check_current_source)))
