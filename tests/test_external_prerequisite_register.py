from pathlib import Path

import pytest

from services.report_safety import validate


def test_external_prerequisite_register_names_required_human_and_institutional_inputs():
    document = Path("docs/remaining-external-evidence.md").read_text(encoding="utf-8")
    for required in (
        "Qualified independent reviewers",
        "Actual clinician correction-time observations",
        "deployment country",
        "patient-data permission",
        "clinical owner",
        "Google client registration",
        "Externally managed encryption keys",
        "regulatory certification",
    ):
        assert required in document
    assert "real-patient release is unauthorized" in document


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"independent_clinical_gold": True, "real_patient_release_authorized": False},
        {"independent_clinical_gold": False, "real_patient_release_authorized": True},
    ],
)
def test_report_policy_never_infers_independent_or_regulatory_approval(report):
    with pytest.raises(ValueError):
        validate(report)


@pytest.mark.parametrize(
    "claim",
    [
        "independent_clinician_evaluation_performed",
        "user_satisfaction_observed",
        "live_oauth_registration_completed",
        "regulatory_review_completed",
    ],
)
def test_report_policy_rejects_unperformed_external_validation_claims(claim):
    with pytest.raises(ValueError, match="unsupported_external_validation_claim"):
        validate(
            {
                "independent_clinical_gold": False,
                "real_patient_release_authorized": False,
                claim: True,
            }
        )


def test_explicitly_unvalidated_report_receives_only_nonclinical_labels():
    assert validate(
        {
            "independent_clinical_gold": False,
            "real_patient_release_authorized": False,
        }
    ) == {
        "safe": True,
        "independent_clinical_gold": False,
        "real_patient_release_authorized": False,
    }
