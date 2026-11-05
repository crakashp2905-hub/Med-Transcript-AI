import hashlib
import json
from pathlib import Path
from services.ollama_inventory import inventory


def test_configured_ollama_blobs_are_hashed_once_and_missing_or_corrupt_stays_visible(tmp_path,monkeypatch):
    import services.ollama_inventory as module
    content=b'synthetic marker, not model weights';digest=hashlib.sha256(content).hexdigest()
    blobs=tmp_path/'blobs';blobs.mkdir();blob=blobs/('sha256-'+digest);blob.write_bytes(content)
    manifest=tmp_path/'manifests/registry.ollama.ai/library/qwen2.5/test';manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'config':{'digest':'sha256:'+digest,'size':len(content)},'layers':[{'digest':'sha256:'+digest,'size':len(content)}]}))
    monkeypatch.setattr(module,'CONFIGURED',{'qwen2.5:test':hashlib.sha256(manifest.read_bytes()).hexdigest(),'qwen2.5:missing':'a'*64})
    result=inventory(tmp_path)
    assert len(result['blobs'])==1 and result['unique_blob_bytes']==len(content)
    assert result['models'][0]['status']=='contents_hashed_not_model_eligibility'
    assert result['models'][1]['status']=='unavailable' and not result['model_inference_performed']
    blob.write_bytes(b'corrupt')
    assert inventory(tmp_path)['models'][0]['status']=='unavailable_or_corrupt_blob'
    blob.unlink()
    assert inventory(tmp_path)['blobs'][0]['status']=='unavailable'


def test_ollama_manifest_and_schema_cannot_redirect_blob_reads(tmp_path,monkeypatch):
    import services.ollama_inventory as module
    path=tmp_path/'manifests/registry.ollama.ai/library/qwen2.5/test';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'config':{'digest':'../../private','size':1},'layers':[]}))
    monkeypatch.setattr(module,'CONFIGURED',{'qwen2.5:test':hashlib.sha256(path.read_bytes()).hexdigest()})
    import pytest
    with pytest.raises(ValueError,match='invalid_cached_blob_descriptor'):inventory(tmp_path)
