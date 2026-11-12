"""Independent research-prototype readiness dimensions; no clinical promotion path."""

LEVELS = (
    "offline_demo",
    "engineering_verified",
    "research_evidence_complete",
    "clinical_approved",
)
P0_BLOCKERS = (
    "unsafe_auto_approval",
    "identity_leakage",
    "missing_audit",
    "corrupted_evidence",
)
EVIDENCE_HIERARCHY = (
    "independent_clinical_labels",
    "non_independent_source_references",
    "developer_synthetic_oracles",
    "model_judgments",
)


def validate_matrix(matrix):
    if set(matrix) != set(LEVELS) or any(
        not isinstance(v, str) for v in matrix.values()
    ):
        raise ValueError("independent_readiness_dimensions_required")
    if matrix["clinical_approved"] != "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED":
        raise ValueError("developer_evidence_cannot_authorize_clinical_release")
    if any(
        v
        not in (
            "verified",
            "failed",
            "not_established",
            "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        )
        for v in matrix.values()
    ):
        raise ValueError("unsupported_release_status")
    return matrix


def engineering_gate(findings):
    if any(f.get("severity") == "P0" or f.get("code") in P0_BLOCKERS for f in findings):
        return {
            "status": "blocked",
            "reason": "unresolved_P0",
            "real_patient_release_authorized": False,
        }
    return {
        "status": "not_established",
        "reason": "full_checklist_and_evidence_still_required",
        "real_patient_release_authorized": False,
    }


def validate_evidence_scope(report, tier):
    if tier not in EVIDENCE_HIERARCHY:
        raise ValueError("unknown_evidence_tier")
    if tier != "independent_clinical_labels" and (
        report.get("independent_clinical_gold") is not False
        or report.get("real_patient_release_authorized") is not False
    ):
        raise ValueError("lower_tier_cannot_impersonate_clinical_evidence")
    return tier
