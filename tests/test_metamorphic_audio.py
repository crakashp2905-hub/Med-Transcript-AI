import pytest

from services.asr.metamorphic import validate_transform


def test_metamorphic_transform_records_source_identity():
    report = validate_transform(
        "mild_resampling",
        source_sha256="a" * 64,
        transformed_sha256="b" * 64,
        result={"status": "measured"},
    )
    assert report["source_integrity_preserved"] is True
    assert report["clinical_claim"] is False


def test_metamorphic_transform_rejects_untracked_variant():
    with pytest.raises(ValueError, match="unknown_metamorphic_transform"):
        validate_transform(
            "untracked", source_sha256="a", transformed_sha256="b", result={}
        )
