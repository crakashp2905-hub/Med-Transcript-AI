"""Provider contracts with explicit limitation disclosure."""

from typing import Protocol


class ProviderResult(Protocol):
    limitations: list[str]


class ASRProvider(Protocol):
    def transcribe(self, audio_path: str) -> ProviderResult: ...


class DiarizationProvider(Protocol):
    def assign_speakers(self, transcript: ProviderResult) -> ProviderResult: ...


class ExtractionProvider(Protocol):
    def extract(self, transcript: ProviderResult) -> ProviderResult: ...


class DraftingProvider(Protocol):
    def draft(self, facts: ProviderResult) -> ProviderResult: ...


class VerificationProvider(Protocol):
    def verify(self, draft: ProviderResult) -> ProviderResult: ...


def require_limitations(result):
    limitations = getattr(result, 'limitations', None)
    if not isinstance(limitations, list) or not limitations or not all(isinstance(x, str) and x.strip() for x in limitations):
        raise ValueError('provider_limitations_required')
    return result
