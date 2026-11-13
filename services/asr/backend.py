"""Truthful backend capability protocol and fail-closed invocation boundary."""

from services.provider_interfaces import ASRProvider, ProviderFailure


class BackendError(ProviderFailure):
    def __init__(self, code):
        kind = (
            "timeout"
            if "timeout" in code
            else "unavailable"
            if "unavailable" in code or "missing" in code
            else "invalid_output"
            if "output_invalid" in code
            else "failed"
        )
        super().__init__("asr", kind, code=code)


ASRBackend = ASRProvider


def inspect_backend(backend):
    methods = (
        "transcribe",
        "availability",
        "timestamp_capability",
        "n_best_capability",
        "confidence_capability",
        "runtime_receipt",
    )
    if not isinstance(backend, ASRProvider) or any(
        not callable(getattr(backend, name, None)) for name in methods
    ):
        raise BackendError("backend_contract_incomplete")
    availability = backend.availability()
    timestamps = backend.timestamp_capability()
    n_best = backend.n_best_capability()
    confidence = backend.confidence_capability()
    receipt = backend.runtime_receipt()
    if not isinstance(availability, dict) or availability.get("status") not in {
        "available_not_admitted",
        "unavailable",
        "integrity_failed",
    }:
        raise BackendError("backend_availability_invalid")
    if (
        not isinstance(timestamps, dict)
        or timestamps.get("kind") not in {"none", "chunk", "segment", "word"}
        or type(timestamps.get("native")) is not bool
    ):
        raise BackendError("backend_timestamp_capability_invalid")
    for name, capability in (("n_best", n_best), ("confidence", confidence)):
        if (
            not isinstance(capability, dict)
            or type(capability.get("supported")) is not bool
        ):
            raise BackendError(f"backend_{name}_capability_invalid")
    if (
        not isinstance(receipt, dict)
        or not isinstance(receipt.get("backend_id"), str)
        or not receipt["backend_id"]
        or not isinstance(receipt.get("runtime_version"), str)
        or not isinstance(receipt.get("model_revision"), str)
    ):
        raise BackendError("backend_runtime_receipt_invalid")
    return {
        "availability": availability,
        "timestamp_capability": timestamps,
        "n_best_capability": n_best,
        "confidence_capability": confidence,
        "runtime_receipt": receipt,
    }


def invoke_backend(backend, source, metadata, checkpoint):
    """Validate declared capabilities before inference and preserve timeout/failure."""
    contract = inspect_backend(backend)
    if contract["availability"]["status"] != "available_not_admitted":
        raise BackendError("backend_unavailable")
    try:
        result = backend.transcribe(source, metadata, checkpoint)
    except TimeoutError:
        raise BackendError("backend_timeout") from None
    if not isinstance(result, dict):
        raise BackendError("backend_output_invalid")
    segments = result.get("segments")
    if segments is not None:
        if not isinstance(segments, list) or any(
            not isinstance(segment, dict) or not isinstance(segment.get("text"), str)
            for segment in segments
        ):
            raise BackendError("backend_output_invalid")
    return {
        "result": result,
        "runtime_receipt": contract["runtime_receipt"],
        "timestamp_capability": contract["timestamp_capability"],
        "n_best_capability": contract["n_best_capability"],
        "confidence_capability": contract["confidence_capability"],
    }
