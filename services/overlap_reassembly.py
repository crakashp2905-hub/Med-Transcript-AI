"""Post-hoc filler-tolerant overlap ablation; all raw hypotheses remain preserved."""
import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
from services.conversation_experiment import join_text,term_counts
from services.evaluation import score

FILLERS={'um','uh','erm','er','yeah','okay','ok','and','so','well','the','a','an','i','it','to','is','you','know'}


def stitch(left,right):
    exact,removed=join_text(left,right,True)
    if removed or not left:return exact,{'method':'exact','removed_tokens':removed}
    a,b=left.split(),right.split()
    normal=lambda s:re.sub(r'[^\w.]','',s.lower())
    best=None
    for m in range(3,min(12,len(a))+1):
        lhs=[normal(x) for x in a[-m:]]
        for n in range(3,min(12,len(b))+1):
            rhs=[normal(x) for x in b[:n]]
            blocks=SequenceMatcher(None,lhs,rhs,autojunk=False).get_matching_blocks()
            matched=sum(block.size for block in blocks)
            if matched<3 or matched/max(m,n)<.7:continue
            ai={i for block in blocks for i in range(block.a,block.a+block.size)}
            bi={i for block in blocks for i in range(block.b,block.b+block.size)}
            if any(lhs[i] not in FILLERS for i in range(m) if i not in ai):continue
            if any(rhs[i] not in FILLERS for i in range(n) if i not in bi):continue
            quality=2*matched-(m+n-2*matched)
            if best is None or (quality,matched,-n)>(best[0],best[1],-best[3]):best=(quality,matched,m,n)
    if best is None:return exact,{'method':'unmatched_retained','removed_tokens':0}
    return ' '.join(a+b[best[3]:]),{'method':'experimental_filler_tolerant','left_suffix_tokens':best[2],
        'removed_tokens':best[3],'matched_tokens':best[1],'requires_audio_review':True}


def run(experiment,output):
    body=Path(experiment).read_bytes();source=json.loads(body)
    if not source['complete']:raise ValueError('Complete original experiment required')
    result={'schema_version':'overlap_reassembly_v1','experiment_sha256':hashlib.sha256(body).hexdigest(),
            'clinical_acceptance':False,'qualified_asr_candidate':False,'output_timestamp_support':False,
            'method':'Legacy exact stitch, then max-12-token suffix/prefix alignment permitting only unmatched fixed-list filler tokens; at least 3 matches and 70% match coverage.',
            'scope':'posthoc_development_reassembly_not_fresh_model_inference_or_acceptance',
            'limitations':['Repeated real speech can be mistaken for duplicated overlap; every fuzzy decision needs audio review.',
                          'No new word/utterance timestamps are generated; input window bounds remain input metadata.',
                          'Reference text is used only after hypothesis assembly for unchanged scoring.'],
            'runs':[],'summary':{}}
    for row in source['runs']:
        if row['mode'] not in ('overlap','speech_aware'):continue
        hypothesis='';events=[]
        for chunk in row['chunks']:
            hypothesis,event=stitch(hypothesis,chunk['hypothesis']);events.append(event)
        scored='' if row['failed'] else hypothesis
        result['runs'].append({'id':row['id'],'mode':row['mode'],'role':row['role'],'failed':row['failed'],
            'reference':row['reference'],'hypothesis':hypothesis,**score(row['reference'],scored),
            'input_coverage_complete':row['input_coverage_complete'],
            'clinical_terms':term_counts(row['reference'],scored),'stitch_events':events})
    for mode in ('overlap','speech_aware'):
        rows=[r for r in result['runs'] if r['mode']==mode]
        words,edits=sum(r['reference_words'] for r in rows),sum(r['normalized_edits'] for r in rows)
        result['summary'][mode]={'reference_words':words,'normalized_edits':edits,'normalized_wer':edits/words,
                                'failed_cases':sum(r['failed'] for r in rows)}
    with Path(output).open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--experiment',required=True)
    p.add_argument('--out',required=True);a=p.parse_args();run(a.experiment,a.out)
