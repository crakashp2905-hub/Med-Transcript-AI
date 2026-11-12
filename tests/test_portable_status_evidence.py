import pytest
from services.engineering_status import evidence_record, evidence_sha256, validate


def test_task_source_evidence_survives_checkout_newlines_but_not_changed_code(tmp_path):
    source = tmp_path / "source.py"
    source.write_bytes(b"value=1\r\n")
    record = evidence_record(source)
    record["path"] = "source.py"
    document = {
        "total": 1,
        "tasks": [
            {
                "id": "x",
                "description": "Synthetic test",
                "status": "verified",
                "evidence": [record],
                "tests": ["test_guard"],
                "limitations": "No clinical claim.",
            }
        ],
    }
    assert validate(document, tmp_path)["verified"] == 1
    source.write_bytes(b"value=1\n")
    assert validate(document, tmp_path)["verified"] == 1
    source.write_bytes(b"value=2\n")
    with pytest.raises(ValueError):
        validate(document, tmp_path)


@pytest.mark.parametrize(
    "name",
    ["evaluation/report.json", "evaluation/report.md", "docs/plans/checklist.md"],
)
def test_frozen_artifact_and_checklist_bytes_cannot_use_source_normalization(
    tmp_path, name
):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"original\r\n")
    record = evidence_record(path)
    assert record["hash_mode"] == "bytes"
    with pytest.raises(ValueError, match="artifact_bytes_cannot_be_normalized"):
        evidence_sha256(path, "normalized_source_text")
    path.write_bytes(b"original\n")
    assert evidence_sha256(path) != record["sha256"]


def test_checkout_parent_name_does_not_change_source_namespace_policy(tmp_path):
    root = tmp_path / "evaluation/checkout"
    root.mkdir(parents=True)
    source = root / "source.py"
    source.write_bytes(b"x=1\r\n")
    assert evidence_record(source, root)["hash_mode"] == "normalized_source_text"
