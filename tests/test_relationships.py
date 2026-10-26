import json
from pathlib import Path
from uuid import uuid4
import pytest
from services.review.relationships import disagreement,analyze_transcript
from services.review.clinical import check_claim

CASES=json.loads(Path('evaluation/clinical-challenge-relations-v2.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_changed_bindings_require_review_and_exact_controls_remain_clear(case):
    findings=check_claim(case['source'],case['claim'])
    assert bool(findings)==case['unsafe']
    if case['unsafe'] and case['category']!='omission':
        assert any(f['code']=='clinical_relationship_disagreement' for f in findings)


def test_relationship_quotes_are_exact_and_never_reviewed():
    text='Patient takes insulin 4 units before lunch and 8 units at bedtime.'
    sid=str(uuid4());result=analyze_transcript({'segments':[{'segment_id':sid,'text':text}]})
    assert len(result['relations'])==2
    for row in result['relations']:
        evidence=row['evidence']
        assert evidence['quote']==text[evidence['start_char']:evidence['end_char']]
        assert evidence['segment_id']==sid
        assert row['review_required'] is True
    assert result['clinical_calibration'] is False


def test_clause_reordering_does_not_change_bindings():
    assert not disagreement('No cough. No fever.','No fever. No cough.')
    assert not disagreement('Take amoxicillin 250 mg orally.','Take amoxicillin 250 mg by mouth.')


def test_structured_slots_cannot_borrow_another_drug_dose_or_reaction():
    from services.review.clinical import check_fact_slots,extract
    assert any(f['field']=='dose_medication_relationship' for f in check_fact_slots('Take amoxicillin 250 mg and warfarin 5 mg.',{'medication_name':'amoxicillin','dose_value':'5','dose_unit':'mg'}))
    assert any(f['field']=='allergy_reaction_relationship' for f in check_fact_slots('Penicillin caused rash. Ibuprofen caused vomiting.',{'allergen':'penicillin','allergy_reaction':'vomiting'}))
    rows=extract({'segments':[{'segment_id':str(uuid4()),'text':'Take amoxicillin 250 mg orally twice daily for five days.'}]})
    assert rows[0]['route']=='orally' and rows[0]['frequency']=='twice daily' and rows[0]['duration']=='five days'
    assert rows[0]['reviewed'] is False
