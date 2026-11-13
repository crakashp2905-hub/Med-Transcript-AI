import pytest

from services.asr.adapter import FasterWhisperAdapter
from services.asr.omi_backend import OmiBackend
from services.asr.parakeet_backend import ParakeetOnnxBackend
from services.review.providers import DeterministicProvider, JSONProvider
from services.offline_adapters import (
    FakeASRAdapter,
    FakeDiarizationAdapter,
    FakeExtractionAdapter,
    FakeVerifierAdapter,
)
from services.review.clinical_models import (
    ClinicalModelFailure,
    LocalClinicalModels,
    RuleExtractor,
)
from services.diarization import LocalDiarizationProvider
from services.asr.backend import BackendError
from services.provider_interfaces import (
    ASRProvider,
    DiarizationProvider,
    DraftingProvider,
    ExtractionProvider,
    VerificationProvider,
    ProviderFailure,
    require_limitations,
    require_provider,
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


def test_each_application_role_implements_its_shared_provider_contract():
    assert isinstance(FakeASRAdapter(()), ASRProvider)
    assert isinstance(LocalDiarizationProvider(), DiarizationProvider)
    assert isinstance(FakeDiarizationAdapter(()), DiarizationProvider)
    assert isinstance(RuleExtractor(), ExtractionProvider)
    assert isinstance(FakeExtractionAdapter(), ExtractionProvider)
    clinical = LocalClinicalModels(enabled=True)
    assert isinstance(clinical, ExtractionProvider)
    assert isinstance(clinical, VerificationProvider)
    assert isinstance(FakeVerifierAdapter(), VerificationProvider)
    assert isinstance(DeterministicProvider(), DraftingProvider)


def test_provider_failures_have_explicit_stage_and_kind():
    asr_error = BackendError("backend_timeout")
    clinical_error = ClinicalModelFailure("clinical_model_unavailable")
    assert (asr_error.stage, asr_error.kind) == ("asr", "timeout")
    assert (clinical_error.stage, clinical_error.kind) == (
        "clinical",
        "unavailable",
    )
    with pytest.raises(ProviderFailure) as error:
        require_provider(object(), DraftingProvider, "drafting")
    assert error.value.code == "drafting_contract_unavailable"


@pytest.mark.parametrize(
    "raised,expected_kind",
    [(TimeoutError("private detail"), "timeout"), (RuntimeError("private"), "failed")],
)
def test_diarization_errors_are_safe_and_stage_specific(
    monkeypatch, raised, expected_kind
):
    import services.diarization as module

    def fail(*args):
        raise raised

    monkeypatch.setattr(module, "diarize", fail)
    with pytest.raises(ProviderFailure) as error:
        LocalDiarizationProvider().diarize("audio", {}, lambda: None)
    assert error.value.stage == "diarization"
    assert error.value.kind == expected_kind
    assert "private" not in str(error.value)


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
