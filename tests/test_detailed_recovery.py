import json
import wave
from pathlib import Path
import pytest
from services.api.ingest import file_sha256
from services.detailed_benchmark import run,evaluate_case

@pytest.mark.parametrize('mode',['speech_aware','context'])
def test_nonfixed_recovery_reuses_verified_cases_and_reruns_unfinished_in_full(tmp_path,monkeypatch,mode):
    monkeypatch.chdir(tmp_path)
    Path('evaluation').mkdir();Path('evaluation/acceptance-reservation-v1.json').write_text(json.dumps({'reserved_groups':[]}))
    audio=tmp_path/'audio.wav'
    with wave.open(str(audio),'wb') as out:
        out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(b'\0\0'*16000)
    cases=[{'group_id':str(i),'foreground_id':str(i),'donor_id':'donor','condition':condition,
        'audio':'audio.wav','audio_sha256':file_sha256(audio),'reference_turns':[{'reference':'No allergy.'}]} for i,condition in enumerate(['clean','distracted'])]
    def predict(path,context):return {'text':'No allergy.','segments':[{'start_ms':0,'end_ms':900,'text':'No allergy.'}]}
    row=evaluate_case(cases[0],audio,predict,mode,lambda row:None)
    previous=tmp_path/'old.json';previous.write_text(json.dumps({'candidate_id':'test','mode':mode,'runtime':{'pinned':True},'manifest_sha256':'unused','cases':[row],'active_case':{'hypothesis':'unfinished must not be reused'}}))
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'split':'development','cases':cases}))
    manifest_sha=file_sha256(manifest)
    data=json.loads(previous.read_text());data['manifest_sha256']=manifest_sha;previous.write_text(json.dumps(data))
    (tmp_path/'lock.json').write_text(json.dumps({'manifest_sha256':manifest_sha}))
    suite=tmp_path/'suite.json';suite.write_text(json.dumps({'manifest':str(manifest),'manifest_sha256':manifest_sha,'maximum_normalized_wer':.05,'source_text_sha256':{},'audio_root':str(tmp_path),'jobs':[{'candidate_id':'test','resume_by_mode':{mode:{'path':str(previous),'sha256':file_sha256(previous)}}}]}))
    calls=[]
    def measured(path,context):calls.append(context);return predict(path,context)
    monkeypatch.setattr('services.detailed_benchmark.load',lambda job:(measured,{'pinned':True},lambda:None))
    output=tmp_path/'new.json';result=run(str(suite),'test',str(output),mode)
    assert result['complete'] and len(result['cases'])==2 and len(calls)==1
    assert result['cases'][0]==row
    assert result['resumed_from']['reused_complete_cases']==['0']
    assert result['resumed_from']['unfinished_case_rerun_in_full'] is True
    assert result['maximum_normalized_wer']==.05 and result['clinical_acceptance'] is False
    with pytest.raises(ValueError):run(str(suite),'test',str(output),mode)
