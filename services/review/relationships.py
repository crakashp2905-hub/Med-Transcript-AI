"""Explicit lexical bindings, not clinical inference or independent gold."""
from collections import Counter
import re
from typing import Literal
from pydantic import Field
from services.review.models import Strict, Evidence
from services.review.clinical import MEDICATION, SYMPTOMS, NEGATION, quantity_signature

ENTITY=re.compile(MEDICATION.pattern+'|'+SYMPTOMS.pattern+r'|\b(?:asthma|diabetes|hypertension|glucose|bleeding)\b',re.I)
SUBJECT=re.compile(r'\b(patient|mother|father|sister|brother|caregiver|maternal|paternal)\b',re.I)
ACTION=re.compile(r'\b(stop|stopped|continue|hold|restart|reduce|increase)\b',re.I)
TIMING=re.compile(r'\b(?:(?:before|after|at)\s+(?:breakfast|lunch|dinner|bedtime)|morning|evening|bedtime|daily|twice daily|once daily|next week|previously|(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:days?|weeks?|months?))\b',re.I)
ROUTE=re.compile(r'\b(?:orally|oral|by mouth|intravenous|intravenously|subcutaneous|subcutaneously|topical|topically)\b',re.I)
NUMBERS=dict(zip(('one','two','three','four','five','six','seven','eight','nine','ten'),map(str,range(1,11))))


class ClinicalRelationship(Strict):
    subject:Literal['patient','mother','father','sister','brother','caregiver','unknown']
    entities:list[str]=Field(max_length=30)
    quantities:list[tuple[str,str]]=Field(max_length=30)
    timing:list[str]=Field(max_length=30)
    routes:list[str]=Field(max_length=30)
    actions:list[str]=Field(max_length=30)
    condition:str=Field(max_length=4000)
    assertion:Literal['affirmed','negated','uncertain']
    evidence:Evidence
    review_required:bool=True
    interpretation:str='explicit_lexical_binding_not_clinical_validation'


def canonical(text):
    text=text.lower()
    for a,b in NUMBERS.items():text=re.sub(r'\b'+a+r'\b',b,text)
    return text


def bindings(text):
    # Never assign a family member or resolve a pronoun by proximity.
    global_drugs=set(m.group().lower() for m in MEDICATION.finditer(text))
    boundary=re.compile(r'(?<=[;.!?])\s+|\b(?:and|but)\b',re.I)
    start=0
    for end in [m.start() for m in boundary.finditer(text)]+[len(text)]:
        raw=text[start:end];quote=raw.strip();a=start+len(raw)-len(raw.lstrip());b=a+len(quote)
        next_match=boundary.match(text,end);start=next_match.end() if next_match else end
        if not quote:continue
        normalized=canonical(quote)
        entities=sorted(set(m.group().lower() for m in ENTITY.finditer(quote)))
        if len(global_drugs)==1 and not MEDICATION.search(quote) and (quantity_signature(quote) or TIMING.search(quote)):
            entities=sorted(set(entities)|global_drugs)
        if not entities:continue
        subjects={m.group().lower() for m in SUBJECT.finditer(quote)}
        subjects={ {'maternal':'mother','paternal':'father'}.get(s,s) for s in subjects}
        subject=next(iter(subjects)) if len(subjects)==1 else 'unknown'
        condition=''
        if re.search(r'\bif\b',normalized):
            if normalized.startswith('if ') and ',' in normalized:condition=normalized[3:].split(',',1)[0].strip()
            else:condition=re.split(r'\bif\b',normalized,maxsplit=1)[1].strip(' .;')
        row={'subject':subject,'entities':entities,
             'quantities':sorted((unit,str(value.normalize())) for (unit,value),count in quantity_signature(quote).items() for _ in range(count)),
             'timing':sorted(m.group().lower() for m in TIMING.finditer(normalized)),
             'routes':sorted({'orally':'oral','by mouth':'oral','intravenously':'intravenous','subcutaneously':'subcutaneous','topically':'topical'}.get(m.group().lower(),m.group().lower()) for m in ROUTE.finditer(quote)),
             'actions':sorted(m.group().lower() for m in ACTION.finditer(quote)),
             'condition':condition,
             'assertion':'uncertain' if re.search(r'\b(?:maybe|possibly|unsure)\b',quote,re.I) else 'negated' if NEGATION.search(quote) else 'affirmed'}
        yield a,b,quote,row


def signature(text):
    import json
    return Counter(json.dumps(row,sort_keys=True) for _,_,_,row in bindings(text))


def disagreement(source,claim):
    a,b=signature(source),signature(claim)
    source_entities=Counter(e for _,_,_,r in bindings(source) for e in r['entities'])
    claim_entities=Counter(e for _,_,_,r in bindings(claim) for e in r['entities'])
    return bool(a and b and source_entities==claim_entities and a!=b)


def analyze_transcript(transcript):
    rows=[]
    for segment in transcript['segments']:
        for a,b,quote,row in bindings(segment['text']):
            rows.append(ClinicalRelationship(**row,evidence=Evidence(segment_id=segment['segment_id'],start_char=a,end_char=b,quote=quote)).model_dump(mode='json'))
    return {'schema_version':'explicit_relationships_v1','relations':rows,
            'limitations':['Limited explicit vocabulary; unrecognized terms are not validated.','Unknown subjects and ambiguous scope require human review.','No relation is an approved clinical fact.'],
            'clinical_calibration':False}
