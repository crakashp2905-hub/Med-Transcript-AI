import hashlib
import json

import pytest

from services.immutable_reports import publish_json_once


def test_publication_is_write_once_and_successor_binds_predecessor_hash(tmp_path):
    first = tmp_path / "report-v1.json"
    original = publish_json_once(first, {"score": 0.2})
    assert original["publication"]["supersedes"] is None
    first_bytes = first.read_bytes()
    with pytest.raises(FileExistsError):
        publish_json_once(first, {"score": 0.0})
    assert first.read_bytes() == first_bytes

    successor = tmp_path / "report-v2.json"
    result = publish_json_once(successor, {"score": 0.1}, supersedes=first)
    assert result["publication"]["supersedes"] == {
        "path": first.as_posix(),
        "sha256": hashlib.sha256(first_bytes).hexdigest(),
    }
    assert json.loads(successor.read_text()) == result


def test_successor_rejects_missing_or_same_path_predecessor(tmp_path):
    path = tmp_path / "report.json"
    with pytest.raises(ValueError, match="report_predecessor_missing"):
        publish_json_once(path, {}, supersedes=tmp_path / "absent.json")
    path.write_text("{}")
    with pytest.raises(ValueError, match="report_successor_must_use_new_path"):
        publish_json_once(path, {}, supersedes=path)
