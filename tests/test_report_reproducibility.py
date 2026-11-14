import hashlib
import json
from pathlib import Path

from services import algorithm_reference, claim_provenance, model_cards
from services.publication_bundle import build as build_publication
from services.report_reproducibility import build_manifest
from services.supplementary_bundle import build as build_supplement


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_input_report_generators_are_byte_for_byte_stable():
    assert build_publication(ROOT) == build_publication(ROOT)
    assert build_supplement(ROOT) == build_supplement(ROOT)
    assert algorithm_reference.build(ROOT) == algorithm_reference.build(ROOT)
    assert model_cards.generate(ROOT) == model_cards.generate(ROOT)
    assert claim_provenance.build(ROOT, "a" * 40) == claim_provenance.build(
        ROOT, "a" * 40
    )


def test_report_manifest_hashes_each_output_and_declares_runtime_variability():
    manifest = build_manifest(ROOT, "b" * 40)
    assert manifest["artifact_count"] == 11
    assert manifest["byte_for_byte_outputs"] == 5
    assert manifest["versioned_snapshot_outputs"] == 6
    assert all(len(row["artifact_sha256"]) == 64 for row in manifest["artifacts"])
    assert all(
        len(row["artifact_source_commit"]) == 40 for row in manifest["artifacts"]
    )
    assert all((ROOT / row["path"]).is_file() for row in manifest["artifacts"])
    sbom = next(
        row for row in manifest["artifacts"] if row["path"].endswith("sbom-v1.json")
    )
    assert "/metadata/timestamp" in sbom["variable_fields"]
    assert (
        "/components (installed Python environment snapshot)" in sbom["variable_fields"]
    )
    assert "Immutable versioned snapshot" in sbom["versioning_rule"]


def test_readiness_receipt_binds_exact_cli_output_hash():
    report = json.loads(
        (ROOT / "evaluation/reports/mta-17-13-readiness-cli-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["source_commit"]
    assert report["runtime"]["cli_output_sha256"]
    output = ROOT / report["output_path"]
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest == report["output_sha256"]
