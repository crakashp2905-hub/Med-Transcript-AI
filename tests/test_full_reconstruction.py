import hashlib
import json
from pathlib import Path
import pytest
from services.full_empty_reconstruction import reconstruct


def source(tmp_path,kind):
    body={'complete':True,'manifest_sha256':'a'*64,'model':{'id':'synthetic'},'cases':[{'id':'case','failed':True,'reference':'one two three','hypothesis':'','reference_words':3,'normalized_edits':3,'chunks':[{'start_ms':0,'end_ms':1000,'failed':False,'hypothesis':'one two'},{'start_ms':1000,'end_ms':1200,'failed':True,'hypothesis':''}]}]}
    original=tmp_path/'original.json';original.write_text(json.dumps(body));raw=original.read_bytes()
    probe=tmp_path/'probe.json';probe.write_text(json.dumps({'complete':True,'experiment_sha256':hashlib.sha256(raw).hexdigest(),'model':body['model'],'probes':[{'id':'case','input_start_ms':1000,'input_end_ms':1200,'reproduced_failure':True,'failure_kind':kind}]}))
    return original,probe,raw


def test_empty_proof_retains_reference_words_and_does_not_qualify_a_model(tmp_path):
    original,proof,raw=source(tmp_path,'wrapper_rejects_empty_native_output');out=tmp_path/'out.json';reconstruct(original,proof,out)
    report=json.loads(out.read_text());assert report['summary']['reference_words']==3 and report['summary']['normalized_edits']==1
    assert not report['qualified_asr_candidate'] and report['output_timestamp_support'] is False
    assert report['cases'][0]['original_case_failed'] is True and original.read_bytes()==raw


def test_other_failures_and_stale_proofs_cannot_be_admitted(tmp_path):
    original,proof,raw=source(tmp_path,'other_runtime_failure');out=tmp_path/'out.json';reconstruct(original,proof,out)
    report=json.loads(out.read_text());assert report['summary']['failed_samples']==1 and report['summary']['normalized_edits']==3
    original.write_bytes(raw+b' ')
    with pytest.raises(ValueError):reconstruct(original,proof,tmp_path/'tampered.json')
