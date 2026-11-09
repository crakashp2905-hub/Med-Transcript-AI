import pytest

from services.report_safety import validate


def test_report_safety_accepts_explicit_developer_labels_and_rejects_omissions():
    assert validate({'independent_clinical_gold': False, 'real_patient_release_authorized': False})['safe']
    assert validate({'clinical_acceptance': False})['safe']
    with pytest.raises(ValueError, match='clinical_gold_flag_required'):
        validate({'real_patient_release_authorized': False})
    with pytest.raises(ValueError, match='clinical_release_flag_required'):
        validate({'independent_clinical_gold': False})
