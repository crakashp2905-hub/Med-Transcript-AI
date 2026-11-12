"""Fail-closed release gate for integrity and clinical verification prerequisites."""

REQUIRED = (
    "migration_ok",
    "evidence_ok",
    "schemas_supported",
    "stale_approvals_absent",
    "critical_verification_complete",
)


def check(state):
    if not isinstance(state, dict):
        raise ValueError("release_state_required")
    missing = [key for key in REQUIRED if state.get(key) is not True]
    return {
        "status": "pass" if not missing else "blocked",
        "missing": missing,
        "clinical_release": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "real_patient_release_authorized": False,
    }
