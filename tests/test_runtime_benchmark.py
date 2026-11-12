import pytest

from services.runtime_benchmark import record


def test_runtime_benchmark_keeps_configuration_and_artifact_provenance():
    result = record(
        threads=4,
        quantization="int8",
        runtime_seconds=2.5,
        memory_bytes=100,
        model_digest="sha256:x",
    )
    assert result["threads"] == 4 and result["quantization"] == "int8"
    assert result["artifact_verified"] is True


def test_runtime_benchmark_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        record(
            threads=0,
            quantization="int8",
            runtime_seconds=1,
            memory_bytes=1,
            model_digest="x",
        )
