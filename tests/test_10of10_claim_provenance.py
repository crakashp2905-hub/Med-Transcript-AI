import json
from pathlib import Path

from services.claim_provenance import build, render_markdown


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "evaluation/claim-provenance/10of10-provenance-v2.json"


def test_claim_ledger_maps_each_explicit_target_to_source_test_commit_and_artifact():
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    regenerated = build(ROOT, value["source_commit"])
    assert regenerated == value
    ids = {claim["claim_id"] for claim in value["claims"]}
    assert len(ids) == len(value["claims"])
    assert {
        "overall-self-contained-engineering-target",
        "architecture-maintainability",
        "reliability-recovery",
        "safety-by-design",
        "research-evaluation-integrity",
        "security-privacy-simulations",
        "ux-reproducibility",
        "documentation-product-clarity",
        "engineering-100-point-total",
        "clinical-10of10-explicit-nonclaim",
        "synthetic-restore-count",
    } <= ids
    for claim in value["claims"]:
        assert claim["source_anchors"]
        assert claim["evidence"]
        for evidence in claim["evidence"]:
            assert evidence["test_id"]
            assert len(evidence["source_commit"]) == 40
            artifact = ROOT / evidence["artifact_path"]
            assert artifact.is_file()
            assert len(evidence["artifact_sha256"]) == 64
    assert (
        next(
            c
            for c in value["claims"]
            if c["claim_id"] == "overall-self-contained-engineering-target"
        )["status"]
        == "not_awarded_target_only"
    )
    assert (
        next(
            c
            for c in value["claims"]
            if c["claim_id"] == "clinical-10of10-explicit-nonclaim"
        )["status"]
        == "explicitly_not_claimed"
    )


def test_markdown_claim_ledger_is_rendered_from_machine_readable_contract():
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    document = (ROOT / "docs/research/claim-provenance-10of10-v2.md").read_text(
        encoding="utf-8"
    )
    assert document == render_markdown(value)
    assert "not_awarded_target_only" in document
    assert "synthetic restore count" in document
