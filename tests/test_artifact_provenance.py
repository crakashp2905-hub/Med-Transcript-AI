import pytest

from services.artifact_provenance import make_provenance, validate_provenance


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
