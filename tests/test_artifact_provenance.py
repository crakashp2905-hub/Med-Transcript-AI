import pytest

from services.artifact_provenance import (
    acceptance_artifact_provenance,
    make_provenance,
    validate_provenance,
)


def test_derived_artifact_provenance_is_complete_and_fail_closed():
    receipt = make_provenance(
        source_commit="abc",
        dataset_sha="data",
        code_sha="code",
        model_digest="model",
        config_digest="config",
        created_at="now",
        status="completed",
        limitations="synthetic only",
        validation_scope="unit test",
    )
    assert validate_provenance(receipt) is True
    assert receipt["real_patient_release_authorized"] is False


def test_provenance_rejects_missing_fields():
    with pytest.raises(ValueError, match="provenance_missing"):
        make_provenance(source_commit="abc")


def test_acceptance_workflow_provenance_binds_source_data_code_and_config():
    receipt = acceptance_artifact_provenance(
        source_commit="a" * 40,
        dataset_manifests=[{"path": "dataset/manifest.json", "sha256": "b" * 64}],
        code_sha="c" * 64,
        config_hashes={"pyproject.toml": "d" * 64},
        created_at="2026-11-12T00:00:00Z",
        status="pass",
        limitations=["synthetic validation only"],
    )
    assert validate_provenance(receipt)
    assert receipt["model_digest"] == "not_used_by_offline_acceptance_workflow"
    assert receipt["validation_scope"] == "developer_synthetic_oracles"
    assert len(receipt["dataset_sha"]) == len(receipt["config_digest"]) == 64
