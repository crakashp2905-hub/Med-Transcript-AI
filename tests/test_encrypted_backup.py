from pathlib import Path
import pytest
pytest.importorskip('cryptography.cobblestone')
from cryptography.cobblestone import Cobblestone128Encryptor
from cryptography.exceptions import InvalidTag
from services.encrypted_backup import crypt_file,encrypted_backup,encrypted_restore
from tests.test_foundation import setup,queue_upload


def test_authenticated_stream_rejects_tamper_truncation_and_wrong_key(tmp_path):
    key=Cobblestone128Encryptor.generate_key();source=tmp_path/'source';source.write_bytes(b'synthetic private content'*5000)
    encrypted=tmp_path/'encrypted';crypt_file(source,encrypted,key)
    assert b'synthetic private content' not in encrypted.read_bytes()
    restored=tmp_path/'restored';crypt_file(encrypted,restored,key,decrypt=True);assert restored.read_bytes()==source.read_bytes()
    for index,data in enumerate((encrypted.read_bytes()[:-1],encrypted.read_bytes()[:-20]+b'changed ciphertext!!')):
        damaged=tmp_path/f'damaged{index}';damaged.write_bytes(data);output=tmp_path/f'bad-output{index}'
        with pytest.raises((InvalidTag,ValueError)):crypt_file(damaged,output,key,decrypt=True)
        assert not output.exists()
    with pytest.raises(InvalidTag):crypt_file(encrypted,tmp_path/'wrong-key',Cobblestone128Encryptor.generate_key(),decrypt=True)
    with pytest.raises(FileExistsError):crypt_file(source,encrypted,key)


def test_encrypted_database_backup_restore_roundtrip(setup,tmp_path):
    client,db,_=setup;eid,upload,_,_=queue_upload(client)
    key=Cobblestone128Encryptor.generate_key();destination=tmp_path/'archive.mtenc'
    receipt=encrypted_backup(db,Path(db).parent/'assets',destination,key)
    assert receipt['encrypted'] is True and receipt['managed_key_custody_verified'] is False
    restored=tmp_path/'restored'
    result=encrypted_restore(destination,restored,db,key)
    assert result['envelope_authenticated'] and not result['real_patient_release_authorized']
    assert (restored/'assets'/f'{upload["id"]}.wav').is_file()
    assert not list(tmp_path.glob('mt-backup-*')) and not list(tmp_path.glob('mt-restore-*'))
