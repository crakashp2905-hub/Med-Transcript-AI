from uuid import uuid4

from services.review.clinical import extract


def extract_with_role(text, role="unknown"):
    return extract(
        {"segments": [{"segment_id": str(uuid4()), "text": text, "role": role}]}
    )


def test_patient_role_is_source_and_patient_is_subject():
    fact = extract_with_role("I have cough.", "patient")[0]

    assert fact["subject"] == "patient"
    assert fact["clinical_source"] == "patient_report"


def test_clinician_source_can_report_patient_or_family_subject():
    patient = extract_with_role("Patient denies fever.", "clinician")[0]
    family = extract_with_role("Mother has diabetes.", "clinician")[0]

    assert patient["subject"] == "patient"
    assert patient["assertion"] == "negated"
    assert patient["clinical_source"] == "clinician_statement"
    assert family["subject"] == "family"
    assert family["clinical_source"] == "clinician_statement"


def test_caregiver_report_and_caregiver_subject_remain_distinct():
    fact = extract_with_role("I take warfarin.", "caregiver")[0]

    assert fact["subject"] == "caregiver"
    assert fact["clinical_source"] == "caregiver_report"


def test_unresolved_pronouns_keep_unknown_subject_and_require_review():
    fact = extract_with_role("She takes warfarin.")[0]

    assert fact["subject"] == "unknown"
    assert fact["uncertainty"] == "ambiguous"
    assert fact["clarification"]
    assert fact["reviewed"] is False
