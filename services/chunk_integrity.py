"""Deterministic validation for resumable media chunks."""


def validate_chunk(
    *,
    payload,
    expected_offset,
    actual_offset,
    expected_digest,
    actual_digest,
    max_bytes=10_000_000,
    is_last=False,
):
    if payload is None:
        return {"accepted": False, "reason": "missing_chunk"}
    if len(payload) > max_bytes:
        return {"accepted": False, "reason": "oversized_chunk"}
    if actual_offset != expected_offset:
        return {"accepted": False, "reason": "offset_mismatch"}
    if expected_digest != actual_digest:
        return {"accepted": False, "reason": "digest_mismatch"}
    if is_last and not payload:
        return {"accepted": False, "reason": "truncated_last_chunk"}
    return {"accepted": True, "reason": None}
