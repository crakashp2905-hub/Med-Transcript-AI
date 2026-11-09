"""Provenance guard for Subjective versus Objective clinical facts."""


def validate(fact):
    section = fact.get('section')
    source = fact.get('clinical_source')
    if section not in ('subjective', 'objective'):
        raise ValueError('invalid_fact_section')
    if section == 'subjective' and source not in ('patient_report', 'unknown'):
        raise ValueError('subjective_source_mismatch')
    if section == 'objective' and source != 'clinician_statement':
        return {'allowed': False, 'reason': 'objective_requires_clinician_source', 'invented_observation': True}
    return {'allowed': True, 'reason': None, 'invented_observation': False}
