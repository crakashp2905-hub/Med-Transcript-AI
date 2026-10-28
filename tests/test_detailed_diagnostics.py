from services.detailed_diagnostics import donor_matches,lexical
from services.detailed_drafting import fixtures


def test_lexical_counts_preserve_units_and_negation_but_do_not_claim_clinical_gold():
    value=lexical('No penicillin allergy. Warfarin 0.5 mg daily.','Penicillin allergy. Warfarin 5 mcg daily.')
    assert value['dose_literal_value_unit']['missing_mentions']=={'0.5 mg':1}
    assert value['dose_literal_value_unit']['extra_mentions']=={'5 mcg':1}
    assert value['negation_words_not_scope']['missing_mentions']=={'no':1}


def test_donor_detector_excludes_phrases_already_in_foreground():
    text='one two three four five six seven eight nine'
    assert donor_matches(text,text,text)==[]
    assert donor_matches('unrelated foreground',text,'Doctor: '+text)


def test_drafting_fixtures_retain_every_source_note_clause_with_exact_evidence():
    note='No penicillin allergy; warfarin 0.5 mg daily.\nMother has diabetes.'
    result=fixtures({'cases':[{'condition':'clean','foreground_id':'one','reference_note':note}]})
    facts=result[0]['facts'];assert len(facts)==3
    for fact in facts:
        evidence=fact['fixture_evidence'];assert note[evidence['start_char']:evidence['end_char']]==evidence['quote']==fact['text']
