import hashlib
from uuid import uuid4
from services.review.engine import findings_for,RULES_VERSION

def test_source_level_critical_warning_links_exact_quote_and_fields():
    source='Patient reports cough and takes warfarin 5 mg.'
    quote='Patient reports cough'
    segment_id=str(uuid4());transcript_id=str(uuid4())
    note={'facts':[{'fact_id':str(uuid4()),'text':quote,'section':'subjective','category':'symptom',
                    'subject':'patient','assertion':'affirmed','temporality':'current','origin':'source_linked',
                    'reviewed':True,'critical_reviewed':True,'excluded':False,'clarification':'',
                    'evidence':{'segment_id':segment_id,'start_char':0,'end_char':len(quote),'quote':quote}}]}
    transcript={'id':transcript_id,'review':{'english_confirmed':True,'source_completeness_reviewed':True,
                'source_review_reason':'Complete synthetic source reviewed.'},
                'segments':[{'segment_id':segment_id,'text':source,'role':'patient'}]}
    findings=findings_for(note,transcript)
    critical=next(item for item in findings if item['code']=='critical_source_omission')
    reference=critical['source_reference']
    excerpt=source[reference['start_char']:reference['end_char']]
    assert excerpt=='warfarin' and reference['segment_id']==segment_id
    assert reference['transcript_version_id']==transcript_id
    assert reference['quote_sha256']==hashlib.sha256(excerpt.encode()).hexdigest()
    assert critical['severity']=='critical' and critical['mismatch_fields']==['source_coverage']
    assert critical['validator_version']==RULES_VERSION
    assert all(item.get('source_reference') for item in findings if item['severity']=='critical')
