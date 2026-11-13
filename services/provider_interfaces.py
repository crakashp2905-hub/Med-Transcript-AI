"""Provider-neutral adapter contracts; implementations disclose limitations."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable


class ProviderFailure(ValueError):
    """Safe, stage-specific provider failure; never stores model/source text."""

    KINDS = {"unavailable", "timeout", "failed", "invalid_output"}

    def __init__(self, stage: str, kind: str, *, code: str | None = None):
        if not stage or not stage.isascii() or not stage.replace("_", "").isalnum():
            raise ValueError("invalid_provider_stage")
        if kind not in self.KINDS:
            raise ValueError("invalid_provider_failure_kind")
        self.stage = stage
        self.kind = kind
        self.code = code or f"{stage}_{kind}"
        super().__init__(self.code)


def require_provider(provider: Any, contract: type[Any], stage: str):
    """Fail closed when an application adapter does not implement its contract."""
    if not isinstance(provider, contract):
        raise ProviderFailure(
            stage, "unavailable", code=f"{stage}_contract_unavailable"
        )
    return provider


class ProviderResult(Protocol):
    limitations: list[str]


@runtime_checkable
class ASRProvider(Protocol):
    """ASR adapter contract. Implementations raise ProviderFailure on safe errors."""

    def transcribe(
        self, source: Any, metadata: Mapping[str, Any], checkpoint: Callable[[], None]
    ) -> Mapping[str, Any]: ...

    def availability(self) -> Mapping[str, Any]: ...

    def timestamp_capability(self) -> Mapping[str, Any]: ...

    def n_best_capability(self) -> Mapping[str, Any]: ...

    def confidence_capability(self) -> Mapping[str, Any]: ...

    def runtime_receipt(self) -> Mapping[str, Any]: ...


@runtime_checkable
class DiarizationProvider(Protocol):
    """Speaker-turn adapter; failures are unavailable, timeout or failed."""

    def diarize(
        self, audio: Any, manifest: Mapping[str, Any], checkpoint: Callable[[], None]
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ExtractionProvider(Protocol):
    """Typed clinical-fact extraction; failures never return partial success."""

    def extract_facts(
        self, transcript: Mapping[str, Any], *, authorized: bool, synthetic: bool
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class DraftingProvider(Protocol):
    """Draft proposal adapter; errors are explicit and do not select a fallback."""

    def draft(
        self, facts: list[dict], *, authorized: bool, synthetic: bool
    ) -> dict: ...


@runtime_checkable
class VerificationProvider(Protocol):
    """Evidence-check adapter; model verdicts remain advisory proposals."""

    def check_claims(
        self, claims: Any, *, authorized: bool, synthetic: bool
    ) -> Mapping[str, Any]: ...


def require_limitations(result):
    limitations = getattr(result, "limitations", None)
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(x, str) and x.strip() for x in limitations)
    ):
        raise ValueError("provider_limitations_required")
    return result
