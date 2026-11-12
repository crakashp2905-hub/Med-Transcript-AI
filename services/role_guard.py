"""Fail-closed role-sensitive claim guard."""


def guard_role_claim(segment, claim):
    if (
        not isinstance(segment, dict)
        or segment.get("role") == "unknown"
        or segment.get("role_status") not in ("clinician_confirmed", "human_confirmed")
    ):
        return {
            "allowed": False,
            "role": "unknown",
            "claim": claim,
            "reason": "role_confirmation_required",
        }
    return {"allowed": True, "role": segment["role"], "claim": claim, "reason": None}
