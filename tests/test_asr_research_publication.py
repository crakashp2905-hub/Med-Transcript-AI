import hashlib
from pathlib import Path

from services.asr_research_publication import build


ROOT = Path(__file__).resolve().parents[1]


def test_research_bundle_rebuilds_source_bound_publication_tables():
    first = build(ROOT)
    second = build(ROOT)
    assert first == second
    assert first["inference_performed"] is False
    assert first["clinical_acceptance"] is False
    assert first["maximum_normalized_wer"] == 0.05
    assert first["all_admission_failures_retained"] is True
    assert len(first["model_cards"]) == 13
    assert len(first["ablation_table"]) == 10
    assert len(first["error_receipt_table"]) == 17
    assert first["negative_experiments"]["entry_count"] == 29
    assert len(first["stratified_uncertainty_table"]) == 171
    for row in first["sources"].values():
        source = ROOT / row["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]
    for relative, digest in first["code_manifest"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    assert all(row["wer_admission"] == "fail" for row in first["ablation_table"])
    sparse = [
        row
        for row in first["stratified_uncertainty_table"]
        if row["low"] is None or row["high"] is None
    ]
    assert sparse


def test_missing_source_receipt_fails_closed(tmp_path):
    root = tmp_path / "empty-repository"
    root.mkdir()
    try:
        build(root)
    except ValueError as exc:
        assert "publication_input_missing_or_outside_root" in str(exc)
    else:
        raise AssertionError("missing source receipt should fail closed")
