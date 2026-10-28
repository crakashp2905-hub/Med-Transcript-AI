"""Pinned, paired full-consultation robustness corpus; never imports saved ASR as gold."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import urllib.request
import wave

REVISION='bcef38c2bc8404d52a2c66a799be778e28216102'
BASE=f'https://huggingface.co/datasets/NYU-OLAB/MedDistractAudio/resolve/{REVISION}/'


def fetch(name,root,expected=None,limit=100_000_000):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or (expected and hashlib.sha256(path.read_bytes()).hexdigest()!=expected):
        with urllib.request.urlopen(BASE+name,timeout=120) as response:data=response.read(limit+1)
        if len(data)>limit:raise ValueError('Dataset file size limit exceeded')
        path.write_bytes(data)
    if expected and hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Dataset artifact changed')
    return path


def select(rows,reserved,count=8):
    chosen=[];seen=set()
    for row in rows:
        if row['item_id'] in reserved or row['donor_id'] in reserved or row['level_db']!=-10 or row['item_id'] in seen:continue
        chosen.append(row);seen.add(row['item_id'])
        if len(chosen)==count:break
    if len(chosen)!=count:raise ValueError('Insufficient eligible pairs')
    return chosen


def decode_flac(data,destination,expected):
    import av
    pcm=bytearray()
    with av.open(io.BytesIO(data)) as container:
        if container.format.name!='flac' or len(container.streams.audio)!=1:raise ValueError('Expected one lossless FLAC stream')
        for frame in container.decode(audio=0):
            if frame.sample_rate!=16000 or len(frame.layout.channels)!=1 or frame.format.name not in ('s16','s16p'):raise ValueError('Unexpected PCM format')
            pcm.extend(frame.to_ndarray().astype('<i2').tobytes())
    if hashlib.sha256(pcm).hexdigest()!=expected:raise ValueError('Published PCM hash mismatch')
    with wave.open(str(destination),'wb') as output:
        output.setparams((1,2,16000,0,'NONE','not compressed'));output.writeframes(pcm)
    return len(pcm)/32


def prepare(root,publication):
    from services.prepare_primock import RAW,intervals,download,ATTRIBUTION
    from services.api.ingest import file_sha256
    root=Path(root);publication=Path(publication)
    if (publication/'manifest.json').exists():raise ValueError('Frozen dataset already exists')
    root.mkdir(parents=True,exist_ok=True);publication.mkdir(parents=True,exist_ok=True)
    release=json.loads(fetch('release_manifest.json',root).read_text())
    files={v['path']:v for v in release['files']}
    for name in ['LICENSE','README.md','protocol/recording_hashes.json','data/audio/pairs.parquet']:
        fetch(name,root,files[name]['sha256'])
    sys.path.insert(0,str(Path('data/dataset-runtime').resolve()))
    import pyarrow.parquet as pq
    reserved=set(json.loads(Path('evaluation/acceptance-reservation-v1.json').read_text())['reserved_groups'])
    pairs=select(pq.read_table(root/'data/audio/pairs.parquet').to_pylist(),reserved)
    selected={p['item_id']:p for p in pairs}
    wanted={f"{p['item_id']}__{variant}" for p in pairs for variant in ('clean',p['distractor_type'])}
    protocol={'schema_version':'detailed_preinference_protocol_v1','dataset_revision':REVISION,
        'selection':'first_eight_foreground_encounters_in_frozen_pair_table_with_minus10dB_donor_not_reserved',
        'groups':[p['item_id'] for p in pairs],'recordings':sorted(wanted),'excluded_foreground_and_donors':sorted(reserved),
        'maximum_normalized_wer':.05,'primary_reference':'original_pinned_human_TextGrid_all_words_markup_removed',
        'primary_condition':'clean','robustness_condition':'paired_minus10dB_foreground_reference_donor_speech_is_contamination',
        'no_saved_asr_or_automated_judgments_as_gold':True,'clinical_acceptance':False}
    (publication/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    hashes={v['recording_id']:v for v in json.loads((root/'protocol/recording_hashes.json').read_text())}
    cases={};turns={}
    for group in selected:
        turns[group]=[]
        for role in ('doctor','patient'):
            path=root/f'{group}_{role}.TextGrid'
            text=download(f'{RAW}/transcripts/{group}_{role}.TextGrid',path,500000).decode('utf-8-sig')
            turns[group].extend({'start_ms':round(a*1000),'end_ms':round(b*1000),'role':role,'reference':text,'uncertain_reference':'<' in text} for a,b,text in intervals(text) if text)
        turns[group].sort(key=lambda v:(v['start_ms'],v['end_ms'],v['role']))
    for name,meta in files.items():
        if not name.startswith('recordings/'):continue
        path=fetch(name,root,meta['sha256'])
        # Read keys before materializing audio; no reserved waveform is decoded.
        table=pq.read_table(path,columns=['recording_id'])
        if not wanted.intersection(table.column('recording_id').to_pylist()):continue
        for row in pq.read_table(path).to_pylist():
            rid=row['recording_id']
            if rid not in wanted:continue
            meta=hashes[rid];group=meta['item_id'];pair=selected[group]
            destination=root/f'{rid}.wav';duration=decode_flac(row['audio']['bytes'],destination,meta['pcm_sha256'])
            if abs(duration/1000-meta['duration_seconds'])>.001:raise ValueError('Duration mismatch')
            cases[rid]={'group_id':rid,'foreground_id':group,'condition':meta['condition'],'audio':destination.name,
                'audio_sha256':file_sha256(destination),'pcm_sha256':meta['pcm_sha256'],'duration_ms':duration,
                'donor_id':meta['donor_id'],'level_db':meta['level_db'],'reference_turns':turns[group],
                'reference_note':pair['reference_note'],'donor_reference':pair['distractor_conversation'],
                'background_start_ms':None if meta['onset'] is None else meta['onset']*1000,
                'background_duration_ms':None if meta['segment_end'] is None else (meta['segment_end']-meta['segment_start'])*1000}
            print(f'Prepared {rid}: {duration/1000:.1f}s',flush=True)
        if len(cases)==len(wanted):break
    if set(cases)!=wanted:raise ValueError('Missing selected full recordings')
    manifest={'dataset_id':'meddistract-full-paired-development-v1','source_revision':REVISION,'license':'CC-BY-4.0',
        'data_class':'approved_public','rights_reviewed':True,'split':'development_not_independent_acceptance',
        'attribution':ATTRIBUTION+'; MedDistractAudio: Vishwanath et al. (2026), https://huggingface.co/datasets/NYU-OLAB/MedDistractAudio',
        'clinician_adjudication':'pending','protocol_sha256':file_sha256(publication/'protocol.json'),
        'cases':[cases[rid] for rid in sorted(cases)],
        'limitations':['Controlled digital overlays of mock consultations, not real clinical overlap.',
            'Eight foregrounds repeated across conditions are eight independent sampling units, not sixteen.',
            'Upstream clinician notes are reference summaries, not exhaustive adjudicated atomic facts.',
            'Day1 excerpts were previously used in development; this is not unseen acceptance.',
            'Foreground-only WER on distracted audio measures selective-transcription robustness; donor words remain errors.']}
    (publication/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (publication/'lock.json').write_text(json.dumps({'manifest_sha256':file_sha256(publication/'manifest.json'),'protocol_sha256':file_sha256(publication/'protocol.json'),'dataset_release_sha256':file_sha256(root/'release_manifest.json')},indent=2)+'\n')
    (publication/'LICENSE').write_bytes((root/'LICENSE').read_bytes())
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default='data/datasets/meddistract-detailed-v1');parser.add_argument('--publication',default='evaluation/datasets/meddistract-detailed-v1');a=parser.parse_args();prepare(a.root,a.publication)
