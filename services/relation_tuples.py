"""Typed clinical relation tuple categories."""

RELATIONS = ('medication_dose_route_frequency_duration_time', 'allergy_reaction', 'subject_diagnosis',
             'anatomy_laterality', 'conditional_instruction')


def validate(relations):
    if not isinstance(relations, list):
        raise ValueError('relations_required')
    invalid = [item for item in relations if item.get('type') not in RELATIONS]
    return {'relations': relations, 'invalid': invalid, 'all_valid': not invalid}
