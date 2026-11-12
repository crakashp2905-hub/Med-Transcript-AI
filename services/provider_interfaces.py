"""Provider-neutral adapter contracts; implementations disclose limitations."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable


class ProviderResult(Protocol):
    limitations: list[str]


@runtime_checkable
class ASRProvider(Protocol):
    """Local or hosted ASR capability contract used by the worker router."""

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
    def diarize(
        self, audio: Any, manifest: Mapping[str, Any], checkpoint: Callable[[], None]
    ) -> Mapping[str, Any]: ...


@runtime_checkable
class ExtractionProvider(Protocol):
    def extract(self, transcript: Mapping[str, Any]) -> Any: ...


@runtime_checkable
class DraftingProvider(Protocol):
    def draft(
        self, facts: list[dict], *, authorized: bool, synthetic: bool
    ) -> dict: ...


@runtime_checkable
class VerificationProvider(Protocol):
    def verify(self, claims: Any, *, synthetic: bool = False) -> Mapping[str, Any]: ...


def require_limitations(result):
    limitations = getattr(result, "limitations", None)
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(x, str) and x.strip() for x in limitations)
    ):
        raise ValueError("provider_limitations_required")
    return result
