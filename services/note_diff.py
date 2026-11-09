"""Meaning-preserving structural diff for generated and deterministic notes."""


def compare(deterministic, generated):
    if not isinstance(deterministic, dict) or not isinstance(generated, dict):
        raise ValueError('note_objects_required')
    keys = sorted(set(deterministic) | set(generated))
    changed, omissions, extras = [], [], []
    for key in keys:
        if key not in generated:
            omissions.append(key)
        elif key not in deterministic:
            extras.append(key)
        elif deterministic[key] != generated[key]:
            changed.append(key)
    return {'deterministic': deterministic, 'generated': generated,
            'changed_meanings': changed, 'omissions': omissions, 'extra_claims': extras,
            'approval_required': bool(changed or omissions or extras)}
