from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from services.supply_chain_bundle import build_bundle


def _bundle():
    return build_bundle(
        ".",
        source_commit="a" * 40,
        now=datetime(2026, 11, 14, tzinfo=timezone.utc),
    )


def test_combined_sbom_includes_local_python_and_npm_inputs_without_audit_claim():
    first = _bundle()["sbom"]
    second = _bundle()["sbom"]
    assert first == second
    assert first["bomFormat"] == "CycloneDX"
    assert first["specVersion"] == "1.5"
    assert first["source_commit"] == "a" * 40
    assert first["components"]
    assert any(item["purl"].startswith("pkg:pypi/") for item in first["components"])
    assert any(item["purl"].startswith("pkg:npm/") for item in first["components"])
    assert first["node_dependency_inventory"]["status"] == (
        "generated_from_local_npm_package_lock"
    )
    assert first["vulnerability_assessment"] == {
        "status": "not_performed",
        "safe_to_use": None,
        "reason": "An SBOM is not a vulnerability scan; no package is represented as audited or safe.",
    }
    digest = hashlib.sha256(
        json.dumps(first["components"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert {"name": "packageInventorySha256", "value": digest} in first["metadata"][
        "properties"
    ]


def test_license_register_preserves_unknowns_and_separates_models_and_datasets():
    register = _bundle()["license_register"]
    assert register["python_packages"]
    assert register["npm_packages"]
    assert register["models"]
    assert register["datasets"]
    assert any(
        item["license_status"] == "unknown" for item in register["python_packages"]
    )
    assert all("rights_concluded" in item for item in register["datasets"])
    assert all(
        "clinical_or_commercial_rights_concluded" in item for item in register["models"]
    )
    assert "not legal advice" in register["scope"]
    models = {item["id"]: item for item in register["models"]}
    assert models["omi-med-stt-v1"]["license_metadata"] == "cc-by-4.0"
    assert (
        models["omi-med-stt-v1"]["license_status"]
        == "metadata_declared_review_required"
    )
    assert models["faster-whisper-large-v3"]["license_status"] == "unknown"


def test_model_cards_and_architecture_matrix_keep_release_claims_bounded():
    bundle = _bundle()
    root = Path(__file__).resolve().parents[1]
    registry_count = len(
        json.loads(
            (root / "evaluation/model-registry.json").read_text(encoding="utf-8")
        )["candidates"]
    )
    cards = bundle["model_cards"]
    assert len(cards["cards"]) == registry_count
    assert cards["maximum_normalized_wer"] == 0.05
    assert cards["clinical_release_gate"] == "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED"
    assert cards["real_patient_release_authorized"] is False

    matrix = bundle["architecture_matrix"]
    assert matrix["frameworks"] == []
    assert matrix["regulatory_conformance_claim"] is False
    assert any(
        row["state"] == "external_evidence_blocked" for row in matrix["controls"]
    )
    assert "receiver_specific_ehr_validation" in matrix["open_gates"]
