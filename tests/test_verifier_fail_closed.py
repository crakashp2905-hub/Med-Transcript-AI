"""Advisory verifier transport/coverage failures cannot clear saved safety gates."""
from uuid import uuid4
import pytest
from services.review.clinical_models import LocalClinicalModels, Verdicts
from services.review.clinical_models import Extraction
from services.strict_json import loads
from tests.test_foundation import setup, headers
from tests.test_review_workflow import prepare, draft, approve


@pytest.mark.parametrize('attack', ['missing', 'duplicate', 'invented_id', 'invented_quote'])
def test_semantic_batches_reject_missing_duplicate_invented_ids_and_quotes(attack):
    first, second = str(uuid4()), str(uuid4())
    claims = [{'fact_id': identifier, 'text': 'No fever.', 'evidence': 'No fever.'} for identifier in (first, second)]
    verdicts = [{'fact_id': identifier, 'label': 'supported', 'evidence_quote': 'No fever.', 'reason': 'Synthetic test.'} for identifier in (first, second)]
    if attack == 'missing':
        verdicts.pop()
    elif attack == 'duplicate':
        verdicts[1]['fact_id'] = first
    elif attack == 'invented_id':
        verdicts[1]['fact_id'] = str(uuid4())
    else:
        verdicts[1]['evidence_quote'] = 'No allergies.'
    class Fake(LocalClinicalModels):
        def complete(self, *args):
            return Verdicts.model_validate({'verdicts': verdicts}), {}
    with pytest.raises(ValueError):
        Fake().check_claims(claims, authorized=True, synthetic=True)


def test_actual_semantic_transport_timeout_preserves_blocking_note_and_approval(setup, monkeypatch):
    client, path, _ = setup
    eid, tx, facts = prepare(client, path, 'Taking warfarin 0.5 mg.')
    facts[0]['text'] = 'Taking warfarin 5 mg.'
    result = draft(client, eid, tx, facts)
    assert result['verification']['gate'] == 'blocked'
    client.app.state.clinical_models = LocalClinicalModels(enabled=True)
    class TimeoutTransport:
        def open(self, *args, **kwargs):
            raise TimeoutError('Synthetic timeout; sensitive provider text must not escape.')
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: TimeoutTransport())
    response = client.post(f'/v1/encounters/{eid}/semantic-checks', headers=headers(),
                           json={'note_version_id': result['note']['id']})
    assert response.status_code == 422
    assert response.json()['code'] == 'semantic_check_failed_no_output_admitted'
    workspace = client.get(f'/v1/encounters/{eid}/workspace', headers=headers()).json()
    assert workspace['verification'] == result['verification']
    assert approve(client, eid, result['note']).status_code == 409


def test_model_parser_bounds_excess_facts_and_confusable_schema_without_rewriting_values():
    fact={'segment_id':str(uuid4()),'quote':'No fever.','category':'symptom','section':'subjective'}
    with pytest.raises(ValueError):
        Extraction.model_validate({'facts':[fact]*101})
    with pytest.raises(ValueError):
        Extraction.model_validate({'facts':[{**fact,'hidden_approval':True}]})
    with pytest.raises(ValueError):
        loads('{"fаcts": []}')
    with pytest.raises(ValueError):
        loads('{"metadata":{"cost":1e999}}')
    assert loads('{"quote":"Quoted β uncertainty stays unchanged."}')['quote']=='Quoted β uncertainty stays unchanged.'
