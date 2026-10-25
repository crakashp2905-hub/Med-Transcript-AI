"""Conservative source-span extraction and a separate contradiction checker.

Rules are development heuristics, not calibrated clinical models.
"""
import re
from collections import Counter
from decimal import Decimal
from uuid import uuid4

NEGATION = re.compile(r"\b(no|not|denies|denied|without|never)\b", re.I)
QUANTITY = re.compile(r"(?<![\w.])(?P<value>\d+(?:\.\d+)?|\.\d+)\s*(?P<unit>mcg|mg|kg|g|ml|l|units)\b", re.I)
MEDICATION = re.compile(r"\b(?:metformin|warfarin|insulin|amoxicillin|penicillin|ibuprofen|paracetamol|lisinopril|atorvastatin)\b", re.I)
SYMPTOMS = re.compile(r'\b(?:pain|cough|fever|headache|nausea|breathlessness|rash|vomiting|diarrhea)\b',re.I)


def quantity_signature(text):
    scales={'mcg':('mass',Decimal('.001')),'mg':('mass',Decimal(1)),
        'g':('mass',Decimal(1000)),'kg':('mass',Decimal(1000000)),
        'ml':('volume',Decimal(1)),'l':('volume',Decimal(1000)),
        'units':('units',Decimal(1))}
    return Counter((scales[m['unit'].lower()][0],Decimal(m['value'])*scales[m['unit'].lower()][1])
                   for m in QUANTITY.finditer(text))


def atomic_spans(text):
    # Only split explicit new assertions. Never distribute an implicit negation.
    boundary=re.compile(r'[;.!?](?=\s|$)(?!\d)|\b(?:and|but)\s+(?=(?:denies|denied|no|not|reports|has|takes|taking|stopped|restart|mother|father|metformin|warfarin|insulin|amoxicillin|penicillin)\b)',re.I)
    start=0
    for match in boundary.finditer(text):
        end=match.end() if text[match.start()] in ';.!?' else match.start()
        raw=text[start:end]
        if raw.strip():
            a=start+len(raw)-len(raw.lstrip());b=end-len(raw)+len(raw.rstrip())
            yield a,b,text[a:b]
        start=match.end()
    raw=text[start:]
    if raw.strip():
        a=start+len(raw)-len(raw.lstrip());b=len(text)-len(raw)+len(raw.rstrip())
        yield a,b,text[a:b]


def extract(transcript):
    result = []
    for segment in transcript["segments"]:
        text = segment["text"]
        # Sentence boundaries preserve decimals. Never resolve pronouns by guessing.
        for start,end,quote in atomic_spans(text):
            if not quote:
                continue
            category = "other"
            for name, pattern in [("allergy", r"allerg|anaphyl|reaction"),
                    ("medication", MEDICATION.pattern+r"|\b(?:taking|takes|stopped|restart|mg|mcg|ml)\b"),
                    ("plan", r"\b(?:plan|order|refer|follow.up|test)\b"),
                    ("symptom", r"\b(?:pain|cough|fever|headache|nausea|breathless)\b")]:
                if re.search(pattern, quote, re.I):
                    category = name
                    break
            uncertain = bool(re.search(r"\b(?:maybe|possibly|unsure|she|he|it)\b", quote, re.I)) or bool(NEGATION.search(quote) and re.search(r'\band\b',quote,re.I))
            fact={"fact_id": str(uuid4()), "category": category,
                "section": "plan" if category == "plan" else "subjective", "text": quote,
                "subject": "family" if re.search(r"\b(?:mother|father|sister|brother)\b", quote, re.I) else "unknown",
                "assertion": "uncertain" if uncertain else "negated" if NEGATION.search(quote) else "affirmed",
                "temporality": "historical" if re.search(r"\b(?:stopped|previously|used to|last month)\b", quote, re.I) else "planned" if re.search(r"\b(?:restart|next week|will)\b", quote, re.I) else "unknown",
                "origin": "source_linked", "reviewed": False, "critical_reviewed": False,
                "extraction_version": "conservative_atomic_spans_v2",
                "clarification": "", "evidence": {"segment_id": segment["segment_id"],
                    "start_char": start, "end_char": end, "quote": quote}}
            medications=list(MEDICATION.finditer(quote));quantities=list(QUANTITY.finditer(quote))
            if category=='medication' and len(medications)==1:
                fact['medication_name']=medications[0].group()
                if len(quantities)==1:
                    fact.update(dose_value=quantities[0]['value'],dose_unit=quantities[0]['unit'])
            if category=='allergy' and len(medications)==1:
                fact['allergen']=medications[0].group()
            side=re.findall(r'\b(?:left|right|bilateral)\b',quote,re.I)
            if len(side)==1:fact['laterality']=side[0].lower()
            result.append(fact)
    return result


def check_claim(source, claim):
    from services.evaluation import tokens
    findings = []
    def add(code):
        findings.append({"code": code, "severity": "critical", "blocks_approval": True,
            "source": source, "claim": claim, "validator": "independent_clinical_rules_v2"})
    if bool(NEGATION.search(source)) != bool(NEGATION.search(claim)):
        add("negation_disagreement")
    if quantity_signature(source) != quantity_signature(claim):
        add("dose_or_unit_disagreement")
    if MEDICATION.findall(source.lower()) != MEDICATION.findall(claim.lower()):
        add("medication_or_allergen_disagreement")
    for group, code in [(r"\b(?:left|right|bilateral)\b", "laterality_disagreement"),
            (r"\b(?:stopped|restart|previously|current|next week)\b", "temporality_disagreement")]:
        if re.findall(group, source.lower()) != re.findall(group, claim.lower()):
            add(code)
    family = r"\b(?:mother|father|sister|brother|family)\b"
    if re.findall(family, source.lower()) != re.findall(family, claim.lower()):
        add("incorrect_attribution")
    def drug_doses(text):
        drugs=list(MEDICATION.finditer(text))
        return [(m.group().lower(),quantity_signature(text[m.end():drugs[i+1].start() if i+1<len(drugs) else len(text)])) for i,m in enumerate(drugs)]
    if MEDICATION.findall(source.lower())==MEDICATION.findall(claim.lower()) and drug_doses(source)!=drug_doses(claim):
        add('medication_dose_assignment_disagreement')
    def polarity(text):
        return {m.group().lower(): bool(NEGATION.search(part))
            for part in re.split(r'\b(?:and|but)\b|[;.!?]',text,flags=re.I) for m in SYMPTOMS.finditer(part)}
    if polarity(source).keys()==polarity(claim).keys() and polarity(source)!=polarity(claim):
        add('negation_scope_disagreement')
    connective = {"patient","reports","report","states","state","i","the","a","an","has","have","is","was","takes","take","and","but"}
    original_words=set(tokens(QUANTITY.sub('',source)))
    claimed_words=set(tokens(QUANTITY.sub('',claim)))
    novel = claimed_words-original_words-connective
    if novel:
        add("unsupported_claim_terms")
    if original_words-claimed_words-connective:
        add('omitted_source_terms')
    return findings


def check_fact_slots(source,fact):
    """Validate supplied structured slots; empty slots are unknown, never invented."""
    findings=[]
    def add(field):
        findings.append({'code':'structured_field_disagreement','field':field,'severity':'critical','blocks_approval':True})
    for field in ('medication_name','allergen','route','frequency','duration','allergy_reaction','anatomical_site','concept'):
        value=fact.get(field)
        if value and not re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',source,re.I):
            add(field)
    value,unit=fact.get('dose_value'),fact.get('dose_unit')
    if value or unit:
        try:
            supplied=quantity_signature(f'{value or ""} {unit or ""}')
            if not supplied or not supplied<=quantity_signature(source):add('dose_value_or_unit')
        except Exception:
            add('dose_value_or_unit')
    if fact.get('laterality','unknown')!='unknown' and not re.search(r'\b'+re.escape(fact['laterality'])+r'\b',source,re.I):
        add('laterality')
    if fact.get('subject')=='patient' and re.search(r'\b(?:mother|father|sister|brother)\b',source,re.I):
        add('subject')
    if fact.get('assertion') in ('affirmed','negated'):
        if len(list(atomic_spans(source)))>1 or (fact['assertion']=='negated')!=bool(NEGATION.search(source)):
            add('assertion')
    historical=bool(re.search(r'\b(?:stopped|previously|used to|last month)\b',source,re.I))
    planned=bool(re.search(r'\b(?:restart|next week|will)\b',source,re.I))
    if historical and fact.get('temporality') in ('current','planned') or planned and not historical and fact.get('temporality') in ('current','historical'):
        add('temporality')
    return findings
