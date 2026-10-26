"""Complete-source Omi development screen; chunk boundaries are not word alignment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import wave

from services.api.ingest import file_sha256
from services.evaluation import score, wer_gate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',default='evaluation/datasets/primock57-full-v1/manifest.json')
    parser.add_argument('--audio-root',default='data/datasets/primock57-full-v1')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    destination=Path(args.out)
    if destination.exists():raise ValueError('Preserve previous benchmark evidence; choose a new output')
    sys.path.insert(0,str(Path('data/benchmark-runtime').resolve()))
    os.environ['OMI_MED_STT_CACHE']=str(Path('data/omi-cache').resolve())
    os.environ['OMI_MED_STT_CPP_REQUIRE_PREBUILT']='1'
    from services.omi_adapter import OmiPredictor
    source=Path(args.manifest)
    manifest=json.loads(source.read_text(encoding='utf-8'))
    reserved=set(json.loads(Path('evaluation/acceptance-reservation-v1.json').read_text())['reserved_groups'])
    if 'human_annotation' in manifest.get('split','') or reserved.intersection(c['group_id'] for c in manifest['cases']):
        raise ValueError('Reserved acceptance audio is not eligible for development inference')
    lock=json.loads((source.parent/'lock.json').read_text(encoding='utf-8'))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=lock['manifest_sha256']:
        raise ValueError('Frozen full-consultation manifest changed')
    original=json.loads(Path('evaluation/runs/primock57-expanded-v1/omi-med-stt-v1.json').read_text(encoding='utf-8'))
    model=Path('data/models/omi-med-stt-v1-gguf').resolve()
    for name,sha in original['runtime_configuration']['artifacts'].items():
        if file_sha256(model/name)!=sha:
            raise ValueError('Model integrity failure')
    predictor=OmiPredictor(model,original['model_revision'])
    report={'dataset_id':manifest['dataset_id'],'manifest_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'model':original['runtime_configuration'],'maximum_normalized_wer':.05,
        'clinical_acceptance':False,'reference_status':'upstream_not_clinician_adjudicated',
        'clinical_metrics_status':'independent_concept_annotations_not_available',
        'reference_rendering':'strip_annotation_markup_retain_all_enclosed_words_v1',
        'limitations':['Fixed non-overlapping 30-second input windows can split words',
            'Input chunk intervals are not word or utterance alignment',
            'Upstream uncertain words and overlapping turns require independent adjudication'], 'cases':[]}
    work=Path('data/full-asr-chunks');work.mkdir(exist_ok=True)
    try:
        for case in manifest['cases']:
            audio=Path(args.audio_root)/case['audio']
            if file_sha256(audio)!=case['audio_sha256']:
                raise ValueError('Source audio integrity failure')
            with wave.open(str(audio),'rb') as stream:
                if (stream.getnchannels(),stream.getframerate(),stream.getsampwidth())!=(1,16000,2):
                    raise ValueError('Invalid source audio')
                pcm=stream.readframes(stream.getnframes())
            chunks=[];start=time.perf_counter()
            for offset in range(0,len(pcm),30*16000*2):
                piece=pcm[offset:offset+30*16000*2]
                path=work/f"{case['group_id']}-{offset//960000:03}.wav"
                with wave.open(str(path),'wb') as out:
                    out.setparams((1,2,16000,0,'NONE','not compressed'));out.writeframes(piece)
                try:
                    hypothesis=predictor(path);failed=False
                except Exception:
                    hypothesis='';failed=True
                chunks.append({'start_ms':offset/32,'end_ms':(offset+len(piece))/32,
                    'hypothesis':hypothesis,'failed':failed})
                print(f"{case['group_id']} chunk {len(chunks)} failed={failed}",flush=True)
            failed=any(c['failed'] for c in chunks)
            reference=' '.join(re.sub(r'<[^>]+>','',t['reference']) for t in case['reference_turns'])
            hypothesis='' if failed else ' '.join(c['hypothesis'] for c in chunks)
            report['cases'].append({'id':case['group_id'],'failed':failed,'reference':reference,
                'hypothesis':hypothesis,'chunks':chunks,'wall_seconds':time.perf_counter()-start,
                **score(reference,hypothesis)})
            summary={'reference_words':sum(c['reference_words'] for c in report['cases']),
                'normalized_edits':sum(c['normalized_edits'] for c in report['cases']),
                'failed_samples':sum(c['failed'] for c in report['cases'])}
            summary['normalized_wer']=summary['normalized_edits']/summary['reference_words']
            report['summary']=summary;report['wer_gate']=wer_gate(summary,.05)
            report['complete']=len(report['cases'])==len(manifest['cases'])
            destination.write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:
        predictor.close()


if __name__=='__main__':
    main()
