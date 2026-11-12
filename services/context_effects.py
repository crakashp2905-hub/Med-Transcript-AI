"""Record context truncation and note-batch quality effects."""


def record(*, context_tokens, batch_size, omissions, hallucinations, runtime_seconds):
    if min(context_tokens, batch_size, omissions, hallucinations, runtime_seconds) < 0:
        raise ValueError("invalid_context_metrics")
    return {
        "context_tokens": context_tokens,
        "batch_size": batch_size,
        "omissions": omissions,
        "hallucinations": hallucinations,
        "runtime_seconds": runtime_seconds,
        "quality_measured": True,
    }
