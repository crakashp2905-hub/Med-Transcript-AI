from copy import deepcopy
import pytest
from services.annotation_workflow import packet, compare
from services.study_analysis import summarize


def review(name):
    result = packet({'dataset_id': 'synthetic', 'cases': [{'group_id': 'a', 'audio': 'a.wav',
        'audio_sha256': 'a'*64, 'duration_ms': 1000,
        'reference_turns': [{'reference': 'No allergy.'}]}]})
    result.update(reviewer_id=name, qualified_reviewer_attestation=True,
                  audio_reviewed_attestation=True, independent_review_attestation=True)
    result['annotations'][0].update(complete=True, concepts=[{
        'annotation_id': 'one', 'category': 'allergy', 'concept': 'allergy',
        'subject': 'patient', 'assertion': 'negated', 'temporality': 'current',
        'evidence': {'turn_index': 0, 'start': 0, 'end': 10, 'quote': 'No allergy'}}])
    return result


def test_independent_comparison_never_auto_certifies_gold():
    a, b = review('first'), review('second')
    assert compare(a, b)['adjudication_required'] is False
    assert compare(a, b)['clinical_gold'] is False
    b['annotations'][0]['concepts'][0]['assertion'] = 'affirmed'
    result = compare(a, b)
    assert result['adjudication_required'] and result['cases'][0]['matched'] == 0


@pytest.mark.parametrize('change', ['identity', 'quote', 'source', 'incomplete', 'attestation', 'duplicate'])
def test_invalid_review_rejected(change):
    a, b = review('first'), review('second')
    if change == 'identity': b['reviewer_id'] = ' FIRST '
    if change == 'quote': b['annotations'][0]['concepts'][0]['evidence']['quote'] = 'Invented'
    if change == 'source': b['source']['cases'][0]['audio_sha256'] = 'b'*64
    if change == 'incomplete': b['annotations'][0]['complete'] = False
    if change == 'attestation': b['audio_reviewed_attestation'] = False
    if change == 'duplicate': b['annotations'].append(deepcopy(b['annotations'][0]))
    with pytest.raises(ValueError): compare(a, b)


def study():
    return {'protocol_sha256': 'a'*64, 'planned_pairs': ['one', 'two', 'three'], 'observations': [
        {'pair_id': 'one', 'mode': 'manual', 'status': 'complete', 'wall_seconds': 100, 'critical_errors': 0},
        {'pair_id': 'one', 'mode': 'assisted', 'status': 'complete', 'wall_seconds': 120, 'critical_errors': 1},
        {'pair_id': 'two', 'mode': 'assisted', 'status': 'failed', 'provider_cost': 0}]}


def test_study_keeps_failure_missingness_and_unknown_cost():
    report = summarize(study())
    assert report['median_seconds_saved_complete_pairs_only'] == -20
    assert report['failed_conditions'] == 1 and report['missing_conditions'] == 3
    assert report['incomplete_pairs'] == 2
    assert report['cost_totals']['hardware_cost'] is None
    assert report['clinical_acceptance'] is False


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -1, True])
def test_nonobserved_or_invalid_times_rejected(value):
    source = study()
    source['observations'][0]['wall_seconds'] = value
    with pytest.raises(ValueError): summarize(source)


def test_duplicate_condition_rejected():
    source = study()
    source['observations'].append(source['observations'][0])
    with pytest.raises(ValueError): summarize(source)


def test_release_inventory_recomputes_all_candidates():
    from pathlib import Path
    from services.release_readiness import assess
    report = assess(Path(__file__).resolve().parents[1])
    assert report['evaluated_candidates'] == 8
    assert report['best_development_candidate'] == 'omi-med-stt-v1'
    assert report['eligible_development_candidates'] == []
    assert report['gates'][0]['status'] == 'fail'
    assert report['real_patient_release_authorized'] is False
    assert report['production_model_selected'] is None


def test_adjudication_binds_reviews_and_requires_resolutions():
    from services.annotation_workflow import adjudicate, digest
    a, b, final = review('first'), review('second'), review('third')
    b['annotations'][0]['concepts'][0]['assertion'] = 'affirmed'
    final['review_sha256'] = [digest(a), digest(b)]
    with pytest.raises(ValueError): adjudicate(a, b, final)
    final['decisions'] = {'a': 'Listened again; explicit negation retained.'}
    assert adjudicate(a, b, final)['clinical_release_authorized'] is False
    b['annotations'][0]['concepts'][0]['temporality'] = 'historical'
    with pytest.raises(ValueError): adjudicate(a, b, final)
