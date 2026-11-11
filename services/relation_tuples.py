"""Typed clinical relation tuple categories."""

RELATIONS = ('medication_dose_route_frequency_duration_time', 'allergy_reaction', 'subject_diagnosis',
             'anatomy_laterality', 'conditional_instruction')


def validate(relations):
    if not isinstance(relations, list):
        raise ValueError('relations_required')
    from services.review.relationships import ClinicalRelationship
    invalid = []
    for item in relations:
        try:
            if not isinstance(item, dict):
                raise ValueError('relationship_object_required')
            if 'type' in item:
                if item['type'] not in RELATIONS or not item.get('evidence'):
                    raise ValueError('typed_relationship_evidence_required')
            else:
                ClinicalRelationship.model_validate(item)
        except ValueError:
            invalid.append(item)
    return {'relations': relations, 'invalid': invalid, 'all_valid': not invalid}
