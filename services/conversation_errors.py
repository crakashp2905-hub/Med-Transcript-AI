"""Reference-turn attribution of lexical edits; not ASR alignment or clinical adjudication."""
import argparse
from array import array
from collections import Counter
import json
from pathlib import Path
import re
from services.api.ingest import file_sha256
from services.evaluation import tokens
from services.conversation_experiment import TERMS


def alignment(reference,hypothesis):
    if max(len(reference),len(hypothesis))>6000:raise ValueError('Diagnostic alignment budget exceeded')
    matrix=[array('H',range(len(hypothesis)+1))]
    for i,left in enumerate(reference,1):
        row=array('H',[i]);prior=matrix[-1]
        for j,right in enumerate(hypothesis,1):
            row.append(min(row[-1]+1,prior[j]+1,prior[j-1]+(left!=right)))
        matrix.append(row)
    i,j=len(reference),len(hypothesis);edits=[]
    while i or j:
        if i and j and reference[i-1]==hypothesis[j-1] and matrix[i][j]==matrix[i-1][j-1]:i-=1;j-=1
        elif i and j and matrix[i][j]==matrix[i-1][j-1]+1:
            edits.append(('substitution',i-1,j-1));i-=1;j-=1
        elif i and matrix[i][j]==matrix[i-1][j]+1:
            edits.append(('deletion',i-1,None));i-=1
        else:
            edits.append(('insertion',max(0,i-1),j-1));j-=1
    return list(reversed(edits))


def analyze(case,reference_turns,full_turns=None):
    full_turns=full_turns if full_turns is not None else reference_turns
    reference=[];provenance=[]
    for index,turn in enumerate(reference_turns):
        words=tokens(re.sub(r'<[^>]+>','',turn['reference']))
        reference.extend(words);provenance.extend([index]*len(words))
    if reference!=tokens(case['reference']):raise ValueError('Diagnostic reference rendering changed')
    hypothesis=[] if case['failed'] else tokens(case['hypothesis'])
    edits=alignment(reference,hypothesis)
    if len(edits)!=case['normalized_edits']:raise ValueError('Diagnostic alignment differs from frozen WER scorer')
    by_role={role:{'reference_words':sum(reference_turns[index]['role']==role for index in provenance),
                   'substitutions':0,'deletions':0,'insertions':0} for role in {t['role'] for t in reference_turns}}
    types=Counter();examples=[];clinical=[];uncertain=overlap=0
    for kind,a,b in edits:
        turn=reference_turns[provenance[a]] if provenance else None
        role=turn['role'] if turn else 'unassigned'
        if role in by_role:by_role[role][kind+'s' if kind!='substitution' else 'substitutions']+=1
        types[kind]+=1
        if turn:
            uncertain+=bool(turn.get('uncertain_reference'))
            overlap+=any(t['role']!=role and max(t['start_ms'],turn['start_ms'])<min(t['end_ms'],turn['end_ms']) for t in full_turns)
        item={'operation':kind,'reference_token':None if kind=='insertion' else reference[a],
              'hypothesis_token':hypothesis[b] if b is not None else None,'reference_turn_index':full_turns.index(turn) if turn else None,
              'reference_role':role,'reference_turn_start_ms':turn['start_ms'] if turn else None,
              'reference_turn_end_ms':turn['end_ms'] if turn else None}
        if len(examples)<100:examples.append(item)
        if any(value and TERMS.fullmatch(value) for value in (item['reference_token'],item['hypothesis_token'])):
            clinical.append(item)
    for row in by_role.values():
        row['normalized_edits']=sum(row[k] for k in ('substitutions','deletions','insertions'))
        row['diagnostic_wer']=row['normalized_edits']/row['reference_words'] if row['reference_words'] else None
    return {'id':case['id'],'failed':case['failed'],'reference_words':len(reference),'normalized_edits':len(edits),
            'edit_types':dict(types),'by_reference_role':by_role,'errors_on_uncertain_reference_turns':uncertain,
            'errors_on_overlapping_reference_turns':overlap,'first_100_error_examples':examples,
            'literal_clinical_term_errors':clinical,
            'limitations':['Insertions are attributed to the preceding reference token role; this is diagnostic, not predicted role accuracy.',
                           'Reference turn bounds locate containing source turns; they are not ASR word timestamps.',
                           'Optimal edit alignment ties follow substitution, deletion, insertion order.',
                           'Uncertain/overlapping counts overlap each other and do not establish error causality.',
                           'Literal lexicon errors do not measure clinical concept correctness.']}


def run(root,output,experiment=None,manifest=None,baseline=None):
    root=Path(root);manifest_path=Path(manifest) if manifest else root/'evaluation/datasets/primock57-full-v1/manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if file_sha256(manifest_path)!=json.loads((manifest_path.parent/'lock.json').read_text())['manifest_sha256']:
        raise ValueError('Frozen source changed')
    truth={c['group_id']:c for c in manifest['cases']}
    baseline_path=Path(baseline) if baseline else root/'evaluation/reports/full-consultation-omi-2026-10-25.json'
    baseline=json.loads(baseline_path.read_text())
    if not baseline.get('complete') or baseline['manifest_sha256']!=file_sha256(manifest_path):raise ValueError('Complete matching baseline required')
    report={'schema_version':'conversation_error_diagnostics_v1','clinical_acceptance':False,
            'manifest_sha256':file_sha256(manifest_path),'inputs':{str(baseline_path.relative_to(root)):file_sha256(baseline_path)},'conditions':[]}
    conditions=[('baseline_fixed30',baseline['cases'])]
    if experiment:
        data=json.loads(Path(experiment).read_text())
        if not data['complete'] or data['manifest_sha256']!=file_sha256(manifest_path):raise ValueError('Complete comparable experiment required')
        report['inputs'][experiment]=file_sha256(experiment)
        conditions.extend((mode,[c for c in data['runs'] if c['mode']==mode]) for mode in data['protocol']['modes'])
    for mode,rows in conditions:
        results=[]
        for row in rows:
            full_turns=truth[row['id']]['reference_turns'];turns=full_turns
            if row.get('role','mixed')!='mixed':turns=[t for t in turns if t['role']==row['role']]
            value=analyze(row,turns,full_turns);value['input_role']=row.get('role','mixed');results.append(value)
        report['conditions'].append({'mode':mode,'cases':results})
    with Path(output).open('x',encoding='utf-8') as out:json.dump(report,out,indent=2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.')
    p.add_argument('--out',required=True);p.add_argument('--experiment');p.add_argument('--manifest');p.add_argument('--baseline');a=p.parse_args();run(a.root,a.out,a.experiment,a.manifest,a.baseline)
