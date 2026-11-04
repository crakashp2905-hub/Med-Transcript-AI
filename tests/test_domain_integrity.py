import json,hashlib,sqlite3
from copy import deepcopy
from pathlib import Path
import pytest
from fastapi import HTTPException
from services.canonical import canonical_json,content_sha256
from services.strict_json import loads
from services.domain_contracts import migrate_legacy,validate_record,Approval
from services.api.record_integrity import decode_record
from tests.test_foundation import setup,headers
from tests.test_review_workflow import prepare,draft,approve


def test_canonical_golden_unicode_decimals_nulls_and_line_endings():
    value={'z':None,'dose':'0.50 mg','number':0.5,'unicode':'café β','line':'a\r\nb'}
    expected='{"dose":"0.50 mg","line":"a\\r\\nb","number":0.5,"unicode":"café β","z":null}'
    assert canonical_json(value)==expected
    assert content_sha256(value)==hashlib.sha256(expected.encode('utf-8')).hexdigest()
    assert content_sha256(dict(reversed(list(value.items()))))==content_sha256(value)
    assert content_sha256({**value,'line':'a\nb'})!=content_sha256(value)
    with pytest.raises(ValueError):canonical_json({'invalid':float('nan')})


@pytest.mark.parametrize('body',['{"facts":[],"facts":[1]}','{"fаcts":[]}','['*33+'0'+']'*33,'{"value":NaN}','{"value":"\\ud800"}'])
def test_untrusted_json_rejects_duplicates_confusable_keys_depth_and_surrogates(body):
    with pytest.raises((ValueError,UnicodeError)):loads(body)


def test_strict_json_preserves_valid_unicode_and_quoted_brackets():
    value={'text':'Literal { [ source ] } café β','dose':'0.5 mg'}
    assert loads(json.dumps(value,ensure_ascii=False))==value
    with pytest.raises(ValueError):loads('"large"',max_bytes=2)


def test_legacy_record_migration_is_copy_only_and_rejects_future_schema(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path)
    note=draft(client,eid,tx,facts)['note'];body={k:v for k,v in note.items() if k!='sha256'}
    legacy=deepcopy(body);legacy.pop('schema_version');before=deepcopy(legacy)
    migrated=migrate_legacy('note',legacy)
    assert migrated['schema_version']=='1.0' and legacy==before
    validate_record('note',legacy)
    with pytest.raises(ValueError):validate_record('note',{**body,'schema_version':'2.0'})
    with pytest.raises(ValueError):migrate_legacy('unknown',body)


def test_persisted_tamper_and_cross_scope_records_block_reads_and_approval(setup):
    client,path,_=setup
    eid,tx,facts=prepare(client,path);note=draft(client,eid,tx,facts)['note']
    with sqlite3.connect(path) as con:
        con.row_factory=sqlite3.Row
        row=dict(con.execute('SELECT * FROM documents WHERE id=?',(note['id'],)).fetchone())
        assert decode_record(row,'note')['id']==note['id']
        forged=dict(row);forged['encounter']='wrong-encounter'
        with pytest.raises(HTTPException):decode_record(forged,'note')
        body=json.loads(row['body']);body['facts'][0]['text']='Tampered synthetic statement.'
        con.execute('DROP TRIGGER documents_immutable')
        con.execute('UPDATE documents SET body=? WHERE id=?',(json.dumps(body),note['id']))
    response=client.get(f'/v1/encounters/{eid}/notes/{note["id"]}',headers=headers())
    assert response.status_code==409
    assert 'Tampered synthetic statement' not in response.text
    assert approve(client,eid,note).status_code==409


def test_request_duplicate_keys_are_rejected_before_mutation(setup):
    client,_,_=setup
    response=client.post('/v1/encounters',headers={**headers(),'Content-Type':'application/json'},content='{"synthetic_data":true,"synthetic_data":false}')
    assert response.status_code==422 and response.json()['code']=='invalid_json_structure'
