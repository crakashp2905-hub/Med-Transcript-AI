import pytest

from services.asr.adapter import FasterWhisperAdapter
from services.asr.omi_backend import OmiBackend
from services.asr.parakeet_backend import ParakeetOnnxBackend
from services.review.providers import DeterministicProvider, JSONProvider
from services.provider_interfaces import (
    ASRProvider,
    DiarizationProvider,
    DraftingProvider,
    ExtractionProvider,
    VerificationProvider,
    require_limitations,
)


def test_all_provider_interfaces_are_declared():
    assert all(
        cls is not None
        for cls in (
            ASRProvider,
            DiarizationProvider,
            DraftingProvider,
            ExtractionProvider,
            VerificationProvider,
        )
    )
    assert require_limitations(type("Result", (), {"limitations": ["local-only"]})())


def test_local_asr_and_drafting_adapters_obey_shared_provider_contracts(tmp_path):
    from services.asr.profiles import ASRProfile, REQUIRED_FILES

    for name in REQUIRED_FILES:
        (tmp_path / name).write_bytes(b"fixture")
    profile = ASRProfile(
        profile_id="provider-contract",
        model_dir=str(tmp_path),
        source="synthetic",
        revision="a" * 40,
        license_id="test-only",
        artifacts={name: "0" * 64 for name in REQUIRED_FILES},
    )
    backends = (
        FasterWhisperAdapter(profile),
        OmiBackend(tmp_path, "local-revision", "model.gguf", "0" * 64, "test-only"),
        ParakeetOnnxBackend(
            tmp_path, "local-revision", {"config.json": "0" * 64}, "test-only"
        ),
    )
    assert all(isinstance(backend, ASRProvider) for backend in backends)

    drafting = (
        DeterministicProvider(),
        JSONProvider(endpoint="http://localhost:1", model="fixture"),
    )
    assert all(isinstance(provider, DraftingProvider) for provider in drafting)


def test_declared_runtime_dependencies_do_not_require_paid_provider_sdks():
    import tomllib
    from pathlib import Path

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    dependencies = project["dependencies"] + [
        dependency
        for group in project.get("optional-dependencies", {}).values()
        for dependency in group
    ]
    paid_provider_sdks = ("openai", "deepgram", "boto3", "amazon-transcribe")
    assert not any(
        sdk in dependency.lower()
        for dependency in dependencies
        for sdk in paid_provider_sdks
    )


def test_provider_result_without_limitations_is_rejected():
    with pytest.raises(ValueError, match="provider_limitations_required"):
        require_limitations(type("Result", (), {"limitations": []})())
