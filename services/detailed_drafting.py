"""Reference-note preservation screen; fixture eligibility is not clinician approval."""
import argparse
import json
from pathlib import Path
import re
import time
import urllib.request

from services.api.ingest import file_sha256
from services.inference_slot import local_inference_slot
from services.review.providers import DeterministicProvider,JSONProvider


def fixtures(manifest):
    output=[]
    for case in manifest['cases']:
        if case['condition']!='clean':continue
        note=case['reference_note'];facts=[]
        # Full source note retained. Units are exact clauses/lines, explicitly
        # not asserted to be independently adjudicated atomic clinical facts.
        for index,match in enumerate(re.finditer(r'[^;\n]+',note)):
            text=match.group().strip()
            if not text:continue
            start=match.start()+len(match.group())-len(match.group().lstrip())
            facts.append({'fact_id':f'f{index+1}','section':'subjective','text':text,'reviewed':True,
                'fixture_evidence':{'source':'upstream_clinician_note','start_char':start,'end_char':start+len(text),'quote':text}})
        if not facts or len(facts)>300:raise ValueError('Invalid fixture unit count')
        output.append({'id':case['foreground_id'],'note':note,'facts':facts})
    return output


def execute(manifest_path,output,models):
    manifest=json.loads(Path(manifest_path).read_text(encoding='utf-8'));cases=fixtures(manifest)
    target=Path(output)
    if target.exists():raise ValueError('Preserve the previous draft screen')
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:available={m['name']:m['digest'] for m in json.load(response)['models']}
    expected={'qwen2.5:1.5b':'65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b','qwen2.5:7b':'845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e'}
    if any(name not in expected or available.get(name)!=expected[name] for name in models):raise ValueError('Pinned public local model unavailable')
    report={'schema_version':'detailed_note_preservation_screen_v1','manifest_sha256':file_sha256(manifest_path),
        'clinical_acceptance':False,'clinician_correction_time_measured':False,'independent_gold_available':False,
        'fixture_reviewed_flag':'offline_fixture_eligibility_only_not_a_clinician_attestation',
        'unitization':'exact_note_lines_or_semicolon_clauses_not_adjudicated_atomic_facts','note_sections':'all_fixture_units_in_subjective_to_isolate_transport_preservation',
        'complete':False,'cases':cases,'deterministic':[],'models':[],'provider_calls_cost_usd':0,'hardware_cost_usd':None}
    def save():target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for case in cases:
        value=DeterministicProvider().draft(case['facts'],authorized=True,synthetic=True)
        report['deterministic'].append({'id':case['id'],'output':value,'exact_preservation':True})
    save()
    for name in models:
        rows=[];entry={'model':name,'digest':expected[name],'runs':rows};report['models'].append(entry)
        provider=JSONProvider('http://127.0.0.1:11434/v1/chat/completions',name,enabled=True,timeout_seconds=60,max_tokens=4096,structured_schema=True)
        for case in cases:
            started=time.perf_counter()
            try:
                result=provider.draft(case['facts'],authorized=True,synthetic=True)
                actual=sorted((s['section'],s['text'],tuple(s['fact_ids'])) for s in result['draft']['statements'])
                expected_statements=sorted((f['section'],f['text'],(f['fact_id'],)) for f in case['facts'])
                row={'id':case['id'],'failed':False,'exact_preservation':actual==expected_statements,'output':result}
            except ValueError:row={'id':case['id'],'failed':True,'exact_preservation':False,'error':'bounded_provider_failure'}
            row['wall_seconds']=time.perf_counter()-started;rows.append(row);save()
            print(json.dumps({'model':name,'id':case['id'],'failed':row['failed'],'exact':row['exact_preservation']}),flush=True)
        entry['failed_cases']=sum(r['failed'] for r in rows);entry['exact_cases']=sum(r['exact_preservation'] for r in rows);save()
    report['complete']=True;save()


def run(manifest_path,output,models):
    # Cooperate with the ASR campaign. Leave CPU/memory-heavy operations serial.
    while True:
        with local_inference_slot() as acquired:
            if acquired:
                try:return execute(manifest_path,output,models)
                finally:
                    for model in models:
                        try:
                            request=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'keep_alive':0}).encode(),headers={'Content-Type':'application/json'})
                            with urllib.request.urlopen(request,timeout=15):pass
                        except OSError:pass
        time.sleep(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',default='evaluation/datasets/meddistract-detailed-v1/manifest.json');p.add_argument('--output',default='evaluation/reports/detailed-drafting-2026-10-29.json');p.add_argument('--models',nargs='+',default=['qwen2.5:1.5b','qwen2.5:7b']);a=p.parse_args();run(a.manifest,a.output,a.models)
