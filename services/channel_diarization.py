"""Two-channel VAD alternative; channel identity is not a confirmed clinical role."""
import argparse
import json
from pathlib import Path
import sys
import time
import wave
from services.api.ingest import file_sha256
from services.diarization_evaluation import score_turns


def run(output):
    sys.path.insert(0,str(Path('data/diarization-runtime').resolve()))
    import numpy as np
    import sherpa_onnx as so
    manifest_path=Path('evaluation/datasets/primock57-full-v1/manifest.json')
    manifest=json.loads(manifest_path.read_text())
    if file_sha256(manifest_path)!=json.loads((manifest_path.parent/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen source changed')
    model=json.loads(Path('data/models/public-diarization-v1/manifest.json').read_text())
    if file_sha256(model['vad']['path'])!=model['vad']['sha256'] or so.__version__!=model['runtime_version']:
        raise ValueError('Pinned VAD integrity failure')
    if Path(output).exists(): raise ValueError('Preserve old evidence')
    report={'schema_version':'two_channel_vad_v1','manifest_sha256':file_sha256(manifest_path),
            'runtime_version':so.__version__,'vad':model['vad'],'complete':False,'cases':[],
            'clinical_acceptance':False,'reference_status':'upstream_channel_labels_not_independent_clinical_adjudication',
            'role_policy':'unconfirmed channel IDs; clinician confirmation required in application',
            'limitations':['Requires separate time-synchronized speaker channels.',
                          'Cross-talk, channel swaps and simultaneous voices on one channel remain possible.',
                          'Optimal scoring mapping is not role confirmation.']}
    for case in manifest['cases']:
        rows=[];start=time.perf_counter();failure=None
        try:
            for index,source in enumerate(case['sources']):
                path=Path('data/datasets/primock57-full-v1')/source['normalized_audio']
                if file_sha256(path)!=source['normalized_sha256']: raise ValueError('Audio hash mismatch')
                with wave.open(str(path),'rb') as stream:
                    if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())!=(1,2,16000):
                        raise ValueError('Wrong channel PCM')
                    samples=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.float32)/32768
                config=so.VadModelConfig();config.silero_vad.model=model['vad']['path']
                config.silero_vad.min_silence_duration=.25;config.silero_vad.min_speech_duration=.25
                config.sample_rate=16000;config.num_threads=2
                detector=so.VoiceActivityDetector(config,buffer_size_in_seconds=30)
                def drain():
                    while not detector.empty():
                        speech=detector.front
                        a,b=round(speech.start/16),min(round((speech.start+len(speech.samples))/16),len(samples)/16)
                        if a<b:rows.append({'start_ms':a,'end_ms':b,'speaker_id':f'channel_{index}',
                                           'role':'unknown','role_status':'unconfirmed'})
                        detector.pop()
                for pos in range(0,len(samples),512):
                    piece=samples[pos:pos+512];detector.accept_waveform(np.pad(piece,(0,512-len(piece))));drain()
                detector.flush();drain()
        except Exception as exc:
            failure=type(exc).__name__
        # A failed consultation is scored as entirely missing, never removed.
        report['cases'].append({'id':case['group_id'],'failed':failure is not None,'failure_type':failure,
                               'segments':rows,'metrics':score_turns(case['reference_turns'],[] if failure else rows),
                               'wall_seconds':time.perf_counter()-start})
        Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(case['group_id'],report['cases'][-1]['metrics']['diarization_error_rate'],flush=True)
    total=sum(c['metrics']['reference_speaker_ms'] for c in report['cases'])
    report['weighted_der']=sum(sum(c['metrics'][k] for k in ('missed_speaker_ms','false_alarm_speaker_ms','confused_speaker_ms')) for c in report['cases'])/total
    report['complete']=True
    Path(output).write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);a=p.parse_args();run(a.out)
