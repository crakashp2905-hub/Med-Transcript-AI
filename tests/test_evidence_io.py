import json
from services.evidence_io import atomic_json


def test_atomic_receipt_retries_transient_windows_sharing_violation(tmp_path,monkeypatch):
    import services.evidence_io as io
    original=io.os.replace;calls=[]
    def sharing_violation(source,target):
        calls.append(1)
        if len(calls)<3:raise PermissionError('Synthetic reader lock')
        return original(source,target)
    monkeypatch.setattr(io.os,'replace',sharing_violation)
    target=tmp_path/'report.json';atomic_json(target,{'complete':True})
    assert json.loads(target.read_text())=={'complete':True}
    assert len(calls)==3 and not list(tmp_path.glob('*.pending'))
