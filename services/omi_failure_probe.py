"""Reproduce failed chunk outputs without changing or rescoring the original experiment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import wave
from services.api.ingest import file_sha256


def probe(experiment,output,manifest='evaluation/datasets/primock57-full-v1/manifest.json',audio_root='data/datasets/primock57-full-v1'):
    body=Path(experiment).read_bytes();source=json.loads(body)
    if not source['complete']:raise ValueError('Wait for the original experiment to finish')
    if Path(output).exists():raise ValueError('Preserve previous probe evidence')
    manifest_path=Path(manifest)
    manifest=json.loads(manifest_path.read_text())
    if file_sha256(manifest_path)!=source['manifest_sha256']:raise ValueError('Source changed')
    cases={c['group_id']:c for c in manifest['cases']}
    model=Path('data/models/omi-med-stt-v1-gguf').resolve()
    for name,sha in source['model']['artifacts'].items():
        if file_sha256(model/name)!=sha:raise ValueError('Model changed')
    sys.path.insert(0,str(Path('data/benchmark-runtime').resolve()))
    os.environ['OMI_MED_STT_CACHE']=str(Path('data/omi-cache').resolve())
    os.environ['OMI_MED_STT_CPP_REQUIRE_PREBUILT']='1'
    from services.omi_adapter import OmiPredictor
    predictor=OmiPredictor(model,source['model']['revision'])
    report={'schema_version':'omi_failure_probe_v1','experiment_sha256':hashlib.sha256(body).hexdigest(),
            'model':source['model'],'complete':False,'clinical_acceptance':False,'probes':[],
            'original_failures_preserved':True}
    work=Path('data/conversation-probe');work.mkdir(exist_ok=True)
    try:
        for row in source.get('runs',source.get('cases',[])):
            row={**row,'role':row.get('role','mixed'),'mode':row.get('mode','baseline_fixed30')}
            row['chunks']=[{**c,'input_start_ms':c.get('input_start_ms',c.get('start_ms')),'input_end_ms':c.get('input_end_ms',c.get('end_ms'))} for c in row['chunks']]
            failures=[c for c in row['chunks'] if c['failed']]
            if not failures:continue
            case=cases[row['id']]
            audio=Path(audio_root)/(case['audio'] if row['role']=='mixed' else f"{row['id']}_{row['role']}.wav")
            expected=case['audio_sha256'] if row['role']=='mixed' else next(c['normalized_sha256'] for c in case['sources'] if c['role']==row['role'])
            if file_sha256(audio)!=expected:raise ValueError('Audio changed')
            with wave.open(str(audio),'rb') as stream:pcm=stream.readframes(stream.getnframes())
            for chunk in failures:
                a,b=round(chunk['input_start_ms']*32),round(chunk['input_end_ms']*32)
                value={'mode':row['mode'],'id':row['id'],'role':row['role'],
                       'input_start_ms':chunk['input_start_ms'],'input_end_ms':chunk['input_end_ms'],
                       'pcm_sha256':hashlib.sha256(pcm[a:b]).hexdigest(),'input_all_zero':not any(pcm[a:b])}
                path=work/'chunk.wav'
                with wave.open(str(path),'wb') as out:
                    out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(pcm[a:b])
                try:
                    value.update(reproduced_failure=False,hypothesis=predictor(path))
                except Exception as exc:
                    message=str(exc)
                    value.update(reproduced_failure=True,error_type=type(exc).__name__,
                        failure_kind='wrapper_rejects_empty_native_output' if message=='parakeet.cpp C API produced an empty transcript for PCM chunk' else 'other_runtime_failure',
                        error_message_sha256=hashlib.sha256(message.encode()).hexdigest())
                report['probes'].append(value)
                Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
                print(row['id'],row['role'],value.get('failure_kind','not_reproduced'),flush=True)
        report['complete']=True
        Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:predictor.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',required=True)
    p.add_argument('--out',required=True);p.add_argument('--manifest',default='evaluation/datasets/primock57-full-v1/manifest.json');p.add_argument('--audio-root',default='data/datasets/primock57-full-v1');a=p.parse_args();probe(a.experiment,a.out,a.manifest,a.audio_root)
