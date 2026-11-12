import json

from services.master_matrix import LEDGER, build


def test_matrix_covers_every_ledger_task_and_declares_unmapped_edges():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    matrix = build(ledger, source_commit="a" * 40)
    assert matrix["total"] == 369
    assert len(matrix["tasks"]) == 369
    assert [row["id"] for row in matrix["tasks"]] == [
        task["id"] for task in ledger["tasks"]
    ]
    assert all(row["owner"] == "AI agent" for row in matrix["tasks"])
    assert all(row["priority"] in {"P0", "P1", "P2"} for row in matrix["tasks"])
    assert all(
        row["task_dependency_mapping"] == "unmapped_pending_manual_audit"
        for row in matrix["tasks"]
    )
    assert matrix["tasks"][0]["suggested_after_sections"] == []
    assert matrix["tasks"][-1]["suggested_after_sections"] == [17]
    assert "not an audited dependency graph" in matrix["dependency_policy"]
    assert matrix["clinical_release_authorized"] is False


def test_default_matrix_binds_the_exact_ledger_bytes():
    import hashlib

    matrix = build(source_commit="b" * 40)
    assert matrix["ledger_hash_representation"] == "raw_source_bytes"
    assert matrix["ledger_sha256"] == hashlib.sha256(LEDGER.read_bytes()).hexdigest()
