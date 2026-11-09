from services.fact_provenance import validate


def test_objective_fact_requires_clinician_source_and_subjective_is_reported():
    assert validate({'section': 'subjective', 'clinical_source': 'patient_report'})['allowed'] is True
    blocked = validate({'section': 'objective', 'clinical_source': 'patient_report'})
    assert blocked['allowed'] is False and blocked['invented_observation'] is True
    assert validate({'section': 'objective', 'clinical_source': 'clinician_statement'})['allowed'] is True
