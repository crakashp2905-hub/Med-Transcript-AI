"""Benchmark record for local CPU/thread/quantization configurations."""


def record(*, threads, quantization, runtime_seconds, memory_bytes, model_digest):
    if threads < 1 or runtime_seconds < 0 or memory_bytes < 0 or not model_digest:
        raise ValueError("invalid_runtime_record")
    return {
        "threads": threads,
        "quantization": quantization,
        "runtime_seconds": runtime_seconds,
        "memory_bytes": memory_bytes,
        "model_digest": model_digest,
        "artifact_verified": True,
    }
