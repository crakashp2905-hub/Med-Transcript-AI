import hashlib
import json
from pathlib import Path
import pytest
from services.verify_scribe_evidence import verify


def test_published_artifact_hashes_match():
    root=Path(__file__).resolve().parents[1]
    result=verify(root,'evaluation/reports/scribe-evidence-index-2026-10-26.json')
    assert result['artifact_files_verified']>10 and result['clinical_release_authorized'] is False


def test_source_newlines_normalized_but_artifact_bytes_strict(tmp_path):
    data=tmp_path/'data.json';data.write_bytes(b'{\r\n}\r\n')
    source=tmp_path/'source.py';source.write_bytes(b'x=1\r\n')
    index={'schema_version':'scribe_evidence_index_v2',
        'artifact_sha256':{'data.json':hashlib.sha256(data.read_bytes()).hexdigest()},
        'source_text_sha256':{'source.py':hashlib.sha256(b'x=1\n').hexdigest()}}
    (tmp_path/'index.json').write_text(json.dumps(index))
    assert verify(tmp_path,'index.json',True)['current_source_checked'] is True
    data.write_bytes(b'{\n}\n')
    with pytest.raises(ValueError,match='Artifact integrity'):verify(tmp_path,'index.json')
