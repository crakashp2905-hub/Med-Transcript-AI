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
