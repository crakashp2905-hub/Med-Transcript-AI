"""Comparable full-source local ASR runs. No model output or WER can approve a note."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import wave

from services.api.ingest import file_sha256
from services.clinical_metrics import character_distance
from services.conversation_experiment import windows,join_text,term_counts
from services.evaluation import tokens,wer_gate
from services.evidence_io import atomic_json


def fast_score(reference,hypothesis):
    a,b=tokens(reference),tokens(hypothesis);raw_a,raw_b=tokens(reference,False),tokens(hypothesis,False)
    if max(len(a),len(b),len(raw_a),len(raw_b))>10000:raise ValueError('Scoring token limit exceeded')
    return {'reference_words':len(a),'hypothesis_words':len(b),'normalized_edits':character_distance(a,b),
        'raw_reference_words':len(raw_a),'raw_edits':character_distance(raw_a,raw_b)}


def load(job):
    runtime=job['runtime'];model=None
    if job.get('package_dir'):sys.path.insert(0,str(Path(job['package_dir']).resolve()))
    if runtime=='whisper':
        from services.asr.profiles import load_profiles
        from faster_whisper import WhisperModel
        import numpy as np
        profile=load_profiles(Path('data')/job['profile_file'])[job['profile_id']]
        if profile.sha256!=job['source_profile_sha256']:raise ValueError('Frozen profile changed')
        profile.verify_artifacts()
        if importlib.metadata.version('faster-whisper')!=profile.runtime_version:raise ValueError('Runtime changed')
        model=WhisperModel(profile.model_dir,device=profile.device,compute_type=profile.compute_type,cpu_threads=profile.cpu_threads,num_workers=1,local_files_only=True)
        def predict(path,context=False):
            with wave.open(str(path),'rb') as stream:pcm=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2')
            segments,_=model.transcribe(pcm.astype(np.float32)/32768,language='en',task='transcribe',beam_size=profile.beam_size,
                temperature=0,vad_filter=False,word_timestamps=False,condition_on_previous_text=context,log_progress=False)
            segments=[{'start_ms':s.start*1000,'end_ms':s.end*1000,'text':s.text.strip()} for s in segments]
            return {'text':' '.join(s['text'] for s in segments),'segments':segments}
        return predict,{'runtime':runtime,'version':profile.runtime_version,'profile_sha256':profile.sha256,'revision':profile.revision,'artifacts':profile.artifacts,'native_segment_timestamps':True},lambda:None
    root=Path(job['model_dir'])
    for name,digest in job['expected_artifacts'].items():
        if file_sha256(root/name)!=digest:raise ValueError('Frozen model artifact changed')
    if runtime=='omi':
        os.environ['OMI_MED_STT_CACHE']=str(Path('data/omi-cache').resolve());os.environ['OMI_MED_STT_CPP_REQUIRE_PREBUILT']='1'
        from services.omi_adapter import OmiPredictor
        model=OmiPredictor(root.resolve(),job['revision'],allow_empty_output=job.get('allow_native_empty',False))
    elif runtime=='onnx':
        import onnx_asr,onnxruntime as ort
        if importlib.metadata.version('onnx-asr')!='0.12.0':raise ValueError('Pinned ONNX runtime changed')
        options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
        recognizer=onnx_asr.load_model('nemo-parakeet-tdt-0.6b-v2',path=str(root.resolve()),quantization='int8',sess_options=options,providers=['CPUExecutionProvider'])
        model=lambda path:recognizer.recognize(str(path))
    elif runtime=='sherpa-qwen3':
        from services.qwen_adapter import QwenPredictor
        model=QwenPredictor(root.resolve(),job['revision'])
    else:raise ValueError('Unsupported public runtime')
    def predict(path,context=False):
        if context:raise ValueError('Context mode requires a native long-form Whisper decoder')
        return {'text':model(path),'segments':None}
    return predict,{'runtime':runtime,'revision':job['revision'],'artifacts':job['expected_artifacts'],'native_segment_timestamps':False,'allow_native_empty':job.get('allow_native_empty',False)},getattr(model,'close',lambda:None)


def coverage(spans,frames):
    end=0
    for a,b in spans:
        if a>end or not 0<=a<b<=frames:return False
        end=max(end,b)
    return bool(spans) and spans[0][0]==0 and end==frames


def evaluate_case(case,audio,predict,mode,checkpoint):
    with wave.open(str(audio),'rb') as incoming:
        if (incoming.getnchannels(),incoming.getframerate(),incoming.getsampwidth())!=(1,16000,2):raise ValueError('Unsupported source profile')
        pcm=incoming.readframes(incoming.getnframes())
    spans=[(0,len(pcm)//2)] if mode=='context' else list(windows(pcm,mode))
    if not coverage(spans,len(pcm)//2):raise ValueError('Source coverage invalid')
    row={'id':case['group_id'],'foreground_id':case['foreground_id'],'condition':case['condition'],'mode':mode,
        'input_sha256':file_sha256(audio),'input_coverage_complete':True,'failed':False,'chunks':[],
        'reference':' '.join(re.sub(r'<[^>]+>','',t['reference']) for t in case['reference_turns'])}
    hypothesis='';started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='mt-full-') as temporary:
        path=Path(temporary)/'window.wav'
        for a,b in spans:
            with wave.open(str(path),'wb') as output:output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(pcm[a*2:b*2])
            t=time.perf_counter();failure=None;segments=None;text=''
            try:
                result=predict(path,mode=='context');text=result['text'];segments=result['segments']
                if not isinstance(text,str) or len(text)>500000:raise ValueError('Invalid text output')
                text.encode('utf-8')
                if segments is not None:
                    valid=all(0<=s['start_ms']<=s['end_ms']<=(b-a)/16 for s in segments)
                    for s in segments:s['start_ms']+=a/16;s['end_ms']+=a/16
                else:valid=None
            except Exception as exc:
                failure=type(exc).__name__;text='';valid=None
            hypothesis,removed=join_text(hypothesis,text,mode in ('overlap','speech_aware'))
            row['chunks'].append({'start_ms':a/16,'end_ms':b/16,'hypothesis':text,'failed':failure is not None,
                'error_type':failure,'native_segments':segments,'native_timestamp_bounds_valid':valid,'stitch_removed_tokens':removed,'wall_seconds':time.perf_counter()-t})
            row['failed']=row['failed'] or failure is not None
            checkpoint(row)
    row['partial_hypothesis_for_diagnostics_only']=hypothesis
    row['hypothesis']='' if row['failed'] else hypothesis
    row.update(fast_score(row['reference'],row['hypothesis']),wall_seconds=time.perf_counter()-started)
    row['term_diagnostics']=term_counts(row['reference'],row['hypothesis'])
    row['timestamp_support']=all(c['native_segments'] is not None for c in row['chunks'])
    row['native_timestamp_bounds_valid']=row['timestamp_support'] and all(c['native_timestamp_bounds_valid'] for c in row['chunks'])
    return row


def summarize(rows):
    words=sum(r['reference_words'] for r in rows);edits=sum(r['normalized_edits'] for r in rows)
    result={'reference_words':words,'normalized_edits':edits,'normalized_wer':edits/words if words else None,
        'failed_samples':sum(r['failed'] for r in rows),'samples':len(rows),'wall_seconds':sum(r['wall_seconds'] for r in rows)}
    result['wer_gate']=wer_gate(result,.05)
    return result


def validated_resume(previous,manifest,config,candidate,mode):
    if previous['candidate_id']!=candidate or previous['mode']!=mode or previous['runtime']!=config:
        raise ValueError('Resume model configuration changed')
    truth={c['group_id']:c for c in manifest['cases']};seen=set()
    for row in previous['cases']:
        if row['id'] in seen or row['id'] not in truth:raise ValueError('Unknown/duplicate resumed case')
        seen.add(row['id']);case=truth[row['id']]
        reference=' '.join(re.sub(r'<[^>]+>','',t['reference']) for t in case['reference_turns'])
        if row['reference']!=reference or row['input_sha256']!=case['audio_sha256'] or row['condition']!=case['condition'] or not row['input_coverage_complete']:
            raise ValueError('Resume source changed or coverage incomplete')
        if row['failed'] and row['hypothesis']!='':raise ValueError('Failed resume must preserve whole-case deletions')
        if any(row[k]!=v for k,v in fast_score(reference,row['hypothesis']).items()):raise ValueError('Resume scoring changed')
    return previous['cases']


def run(suite_path,candidate,output,mode='fixed'):
    suite=json.loads(Path(suite_path).read_text());manifest_path=Path(suite['manifest']);manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    lock=json.loads((manifest_path.parent/'lock.json').read_text())
    if file_sha256(manifest_path)!=suite['manifest_sha256'] or suite['manifest_sha256']!=lock['manifest_sha256']:raise ValueError('Frozen dataset changed')
    if suite['maximum_normalized_wer']!=.05:raise ValueError('The 5% gate is unchanged')
    import hashlib
    for name,digest in suite['source_text_sha256'].items():
        if hashlib.sha256(Path(name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()!=digest:raise ValueError('Frozen execution source changed')
    reserved=set(json.loads(Path('evaluation/acceptance-reservation-v1.json').read_text())['reserved_groups'])
    if 'human_annotation' in manifest['split'] or any(c['foreground_id'] in reserved or c['donor_id'] in reserved for c in manifest['cases']):raise ValueError('Acceptance cohort must remain blinded')
    job=next(j for j in suite['jobs'] if j['candidate_id']==candidate)
    destination=Path(output)
    if destination.exists():raise ValueError('Preserve existing run; choose a new output')
    destination.parent.mkdir(parents=True,exist_ok=True)
    report={'schema_version':'detailed_full_asr_v1','candidate_id':candidate,'manifest_sha256':suite['manifest_sha256'],
        'suite_sha256':file_sha256(suite_path),'mode':mode,'complete':False,'cases':[],
        'scoring_profile':'lowercase_words_preserve_decimals_units_negation_v1','failure_policy':'any_failed_chunk_empty_whole_case_all_reference_deletions',
        'maximum_normalized_wer':.05,'clinical_acceptance':False,'runtime':None,'active_case':None}
    def save():
        atomic_json(destination,report)
    save();t=time.perf_counter()
    try:predict,config,close=load(job)
    except Exception as exc:
        report['initialization_failure']=type(exc).__name__;save();raise
    report['runtime']=config;report['model_load_seconds']=time.perf_counter()-t
    try:
        if mode=='fixed' and job.get('resume_from'):
            resume=job['resume_from'];path=Path(resume['path'])
            if file_sha256(path)!=resume['sha256']:raise ValueError('Original resume receipt changed')
            previous=json.loads(path.read_text(encoding='utf-8'))
            if previous['manifest_sha256']!=suite['manifest_sha256']:raise ValueError('Resume dataset changed')
            report['cases']=validated_resume(previous,manifest,config,candidate,mode)
            report['resumed_from']={**resume,'reused_complete_cases':[r['id'] for r in report['cases']],
                'unfinished_case_rerun_in_full':True,'latency_scope':'includes_original_completed_case_measurements_not_a_fresh_whole_corpus_run'}
            save()
        for case in manifest['cases']:
            if any(r['id']==case['group_id'] for r in report['cases']):continue
            audio=Path(suite['audio_root'])/case['audio']
            if file_sha256(audio)!=case['audio_sha256']:raise ValueError('Source waveform changed')
            def checkpoint(row):
                report['active_case']=row;save();print(json.dumps({'candidate':candidate,'id':case['group_id'],'chunks':len(row['chunks']),'last_failed':row['chunks'][-1]['failed']}),flush=True)
            row=evaluate_case(case,audio,predict,mode,checkpoint);report['cases'].append(row);report['active_case']=None
            report['conditions']={condition:summarize([r for r in report['cases'] if r['condition']==condition]) for condition in ('clean','distracted')}
            report['complete']=len(report['cases'])==len(manifest['cases']);save()
    finally:close()
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--suite',default='evaluation/detailed-suite-v2.json');p.add_argument('--candidate',required=True);p.add_argument('--output',required=True);p.add_argument('--mode',choices=['fixed','overlap','speech_aware','context'],default='fixed');a=p.parse_args();run(a.suite,a.candidate,a.output,a.mode)
