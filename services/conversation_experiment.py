"""Complete-audio Omi chunking ablation. Window bounds are never ASR timestamps."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import wave

from services.api.ingest import file_sha256
from services.evaluation import score

TERMS = re.compile(r'\b(?:paracetamol|metformin|warfarin|penicillin|insulin|allergies|allergy|diarrhoea|diarrhea|gastroenteritis|dehydrated|cancer|blood|vomiting|fever|pain)\b', re.I)


def windows(pcm, mode, rate=16000):
    """Energy-selected boundaries, no reference text or annotation-driven selection."""
    import array
    samples = array.array('h', pcm)
    if sys.byteorder != 'little': samples.byteswap()
    count, start = len(samples), 0
    while start < count:
        end = min(count, start+30*rate)
        if mode == 'speech_aware' and end < count:
            # Minimum 100ms RMS over the last five seconds; no samples are skipped.
            candidates = range(start+25*rate, end, rate//10)
            end = min(candidates, key=lambda p: sum(x*x for x in samples[p:p+rate//10]))+rate//20
        yield start, end
        if end == count: break
        start = end if mode == 'fixed' else max(start+rate, end-2*rate)


def join_text(left, right, overlap):
    if not overlap or not left: return (left+' '+right).strip(), 0
    a, b = left.split(), right.split()
    normalize = lambda s: re.sub(r'[^\w.]', '', s.lower())
    for length in range(min(30, len(a), len(b)), 0, -1):
        if [normalize(x) for x in a[-length:]] == [normalize(x) for x in b[:length]]:
            return ' '.join(a+b[length:]), length
    return (left+' '+right).strip(), 0


def term_counts(reference, hypothesis):
    a, b = Counter(x.lower() for x in TERMS.findall(reference)), Counter(x.lower() for x in TERMS.findall(hypothesis))
    return {'lexicon': TERMS.pattern, 'reference_mentions': sum(a.values()),
            'missing_mentions': dict(a-b), 'extra_mentions': dict(b-a),
            'limitation': 'Literal development term counts, not clinical concept correctness or adjudicated errors'}


def run(output, modes, resume_from=None):
    import hashlib
    sys.path.insert(0, str(Path('data/benchmark-runtime').resolve()))
    os.environ['OMI_MED_STT_CACHE'] = str(Path('data/omi-cache').resolve())
    os.environ['OMI_MED_STT_CPP_REQUIRE_PREBUILT'] = '1'
    from services.omi_adapter import OmiPredictor
    path = Path('evaluation/datasets/primock57-full-v1/manifest.json')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if file_sha256(path) != json.loads((path.parent/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen source changed')
    baseline = json.loads(Path('evaluation/reports/full-consultation-omi-2026-10-25.json').read_text())
    model = Path('data/models/omi-med-stt-v1-gguf').resolve()
    for name, sha in baseline['model']['artifacts'].items():
        if file_sha256(model/name) != sha: raise ValueError('Model integrity failure')
    if Path(output).exists(): raise ValueError('Preserve old experiment; choose a new output')
    result = {'schema_version': 'conversation_ablation_v1', 'manifest_sha256': file_sha256(path),
              'model': baseline['model'], 'maximum_normalized_wer': .05, 'complete': False,
              'clinical_acceptance': False, 'output_timestamp_support': False,
              'protocol': {'modes': modes, 'max_window_seconds': 30, 'overlap_seconds': 2,
                           'boundary_search_seconds': 5, 'stitch': 'exact_normalized_suffix_prefix_max30tokens'},
              'reference_status': 'upstream_mock_not_independently_adjudicated', 'runs': []}
    if resume_from:
        previous=json.loads(Path(resume_from).read_text(encoding='utf-8'))
        if any(previous[k]!=result[k] for k in ('schema_version','manifest_sha256','model','protocol')):
            raise ValueError('Resume configuration changed')
        if len({(r['mode'],r['id'],r['role']) for r in previous['runs']})!=len(previous['runs']):
            raise ValueError('Duplicate resumed rows')
        result['resumed_from']={'path':resume_from,'sha256':file_sha256(resume_from),
                                'reason':'prior_runner_stopped_after_completed_case_when_printing_missing_summary_key'}
        result['runs']=previous['runs']
    predictor = OmiPredictor(model, baseline['model']['revision'])
    work = Path('data/conversation-experiment'); work.mkdir(exist_ok=True)
    def save(): Path(output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    try:
        for mode in modes:
            for case in manifest['cases']:
                sources = case['sources'] if mode == 'two_channel' else [{'role': 'mixed', 'normalized_audio': case['audio'], 'normalized_sha256': case['audio_sha256']}]
                for source in sources:
                    audio = Path('data/datasets/primock57-full-v1')/source['normalized_audio']
                    if file_sha256(audio) != source['normalized_sha256']: raise ValueError('Audio changed')
                    with wave.open(str(audio), 'rb') as stream:
                        if (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) != (1,16000,2): raise ValueError('Wrong PCM format')
                        pcm = stream.readframes(stream.getnframes())
                    turns = [t for t in case['reference_turns'] if source['role'] == 'mixed' or t['role'] == source['role']]
                    reference = ' '.join(re.sub(r'<[^>]+>', '', t['reference']) for t in turns)
                    old=next((r for r in result['runs'] if (r['id'],r['mode'],r['role'])==(case['group_id'],mode,source['role'])),None)
                    if old:
                        if old['reference']!=reference or not old['input_coverage_complete']:
                            raise ValueError('Resumed reference/coverage changed')
                        expected=score(reference,'' if old['failed'] else old['hypothesis'])
                        if any(old[k]!=v for k,v in expected.items()):raise ValueError('Resumed scores changed')
                        old['normalized_wer']=old['normalized_edits']/old['reference_words']
                        continue
                    row = {'id': case['group_id'], 'mode': mode, 'role': source['role'], 'reference': reference,
                           'chunks': [], 'duration_ms': len(pcm)/32, 'hypothesis': '', 'failed': False}
                    started = time.perf_counter()
                    for a, b in windows(pcm, 'speech_aware' if mode == 'two_channel' else mode):
                        chunk = work/'current.wav'
                        with wave.open(str(chunk), 'wb') as target:
                            target.setparams((1,2,16000,0,'NONE','not compressed')); target.writeframes(pcm[a*2:b*2])
                        try:
                            text, failed = predictor(chunk), False
                        except Exception as exc:
                            text, failed = '', True
                        row['failed'] |= failed
                        row['hypothesis'], removed = join_text(row['hypothesis'], text, mode != 'fixed')
                        row['chunks'].append({'input_start_ms': a/16, 'input_end_ms': b/16,
                                              'hypothesis': text, 'failed': failed, 'stitched_duplicate_tokens': removed})
                    # Failure-inclusive score: a processing failure yields an empty scored output.
                    scored = '' if row['failed'] else row['hypothesis']
                    row.update(score(reference, scored), clinical_terms=term_counts(reference, scored), wall_seconds=time.perf_counter()-started)
                    row['normalized_wer']=row['normalized_edits']/row['reference_words']
                    end = 0
                    for c in row['chunks']:
                        if c['input_start_ms'] > end or c['input_end_ms'] <= c['input_start_ms']: raise ValueError('Coverage gap')
                        end = max(end, c['input_end_ms'])
                    row['input_coverage_complete'] = math.isclose(end, row['duration_ms'])
                    if not row['input_coverage_complete']: raise ValueError('Incomplete input coverage')
                    result['runs'].append(row); save()
                    print(mode, row['id'], row['role'], 'WER', row['normalized_wer'], flush=True)
        result['complete'] = True
        result['summary'] = {}
        for mode in modes:
            rows = [r for r in result['runs'] if r['mode'] == mode]
            words, edits = sum(r['reference_words'] for r in rows), sum(r['normalized_edits'] for r in rows)
            result['summary'][mode] = {'reference_words': words, 'normalized_edits': edits,
                                      'normalized_wer': edits/words, 'failed_runs': sum(r['failed'] for r in rows),
                                      'passes_development_wer': edits/words <= .05,
                                      'all_input_coverage_complete': all(r['input_coverage_complete'] for r in rows)}
        result['baseline_mixed_fixed30'] = baseline['summary']
        save()
    finally: predictor.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--modes', nargs='+', choices=['fixed','overlap','speech_aware','two_channel'], default=['overlap','speech_aware','two_channel'])
    parser.add_argument('--resume-from')
    args = parser.parse_args(); run(args.out, args.modes,args.resume_from)
