import hashlib
import pytest
from services.offline_preflight import inventory_models


def test_model_inventory_hashes_bytes_without_claiming_model_eligibility(tmp_path):
    model=tmp_path/'data/models/fixture';model.mkdir(parents=True)
    artifact=model/'model.bin';artifact.write_bytes(b'not-a-real-model')
    report=inventory_models(tmp_path,True)
    assert report[0]['files']==[{'path':'data/models/fixture/model.bin','bytes':16,'sha256':hashlib.sha256(b'not-a-real-model').hexdigest()}]
    assert report[0]['status']=='contents_hashed_not_model_eligibility'
    artifact.write_bytes(b'changed-artifact')
    assert inventory_models(tmp_path,True)[0]['files'][0]['sha256']!=report[0]['files'][0]['sha256']
    assert inventory_models(tmp_path,False)[0]['status']=='directory_present_not_a_weight_verification'
    assert inventory_models(tmp_path/'absent',True)==[]


def test_model_inventory_rejects_files_that_change_during_streaming(tmp_path,monkeypatch):
    import services.offline_preflight as module
    model=tmp_path/'data/models/fixture';model.mkdir(parents=True)
    artifact=model/'model.bin';artifact.write_bytes(b'initial')
    original=module.sha256
    def mutate(path):
        digest=original(path);path.write_bytes(b'changed-after-hash');return digest
    monkeypatch.setattr(module,'sha256',mutate)
    with pytest.raises(ValueError,match='model_changed_during_inventory'):
        inventory_models(tmp_path,True)
