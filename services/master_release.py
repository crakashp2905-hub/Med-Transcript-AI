"""Five distinct readiness tiers for the in-house programme."""

TIERS = (
    "local_demo",
    "engineering_verified",
    "research_supported",
    "pilot_candidate",
    "clinical_approved",
)


def assess(
    *,
    current_demo_pass=False,
    exact_commit_ci_pass=False,
    independent_clinical_gold=False,
    asr_five_percent_gate_pass=False,
    institutional_pilot_signoff=False,
):
    """A model verdict or synthetic fixture cannot supply external evidence."""
    engineering = current_demo_pass and exact_commit_ci_pass
    research = engineering and independent_clinical_gold and asr_five_percent_gate_pass
    pilot = research and institutional_pilot_signoff
    values = {
        "local_demo": (current_demo_pass, "current_source_demo_required"),
        "engineering_verified": (engineering, "exact_commit_ci_required"),
        "research_supported": (
            research,
            "independent_clinical_gold_and_five_percent_asr_required",
        ),
        "pilot_candidate": (pilot, "institutional_pilot_signoff_required"),
    }
    tiers = {
        name: {"status": "verified" if passed else "not_established", "reason": reason}
        for name, (passed, reason) in values.items()
    }
    tiers["clinical_approved"] = {
        "status": "BLOCKED_EXTERNAL_EVIDENCE_REQUIRED",
        "reason": "external_clinical_and_regulatory_review_not_performed",
    }
    return {
        "schema_version": "master_release_tiers_v1",
        "tiers": tiers,
        "real_patient_release_authorized": False,
    }
